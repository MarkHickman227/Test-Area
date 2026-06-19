import json
import logging
import re
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import Settings
from app.models import Preferences
from app.services.agency import detect_agency

logger = logging.getLogger(__name__)

_JOB_TYPE_PATTERNS = {
    "CONTRACT": re.compile(
        r"\b(?:contract|freelance|ftc|fixed[\s-]?term|interim|c2c)\b", re.IGNORECASE
    ),
    "PERM": re.compile(
        r"\b(?:permanent|perm|full[\s-]?time|salaried)\b", re.IGNORECASE
    ),
}

SEARCH_PROMPT_TEMPLATE = (
    "Search for recent job postings matching these criteria. "
    "Return ONLY a JSON array of objects with these exact keys: "
    "title, company, location, salary_text, description, source_url, job_type. "
    "Each object represents one real job posting. "
    "Return between 3 and 10 results. No commentary outside the JSON array.\n\n"
    "Search criteria:\n"
    "- Titles: {titles}\n"
    "- Locations: {locations}\n"
    "- Seniority: {seniority}\n"
    "- Job types: {job_types}\n"
    "- Industries: {industries}\n"
    "{salary_line}"
)


class DiscoveryService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def search_jobs(self, preferences: Preferences) -> list[dict[str, Any]]:
        if not self.settings.perplexity_configured:
            logger.info("Skipping discovery — PERPLEXITY_API_KEY not configured")
            return []

        prompt = self._build_prompt(preferences)
        raw = await self._call_perplexity(prompt)
        return self._parse_results(raw)

    def _build_prompt(self, prefs: Preferences) -> str:
        salary_line = ""
        if prefs.salary_min:
            salary_line = f"- Minimum salary: £{prefs.salary_min:,}\n"
        return SEARCH_PROMPT_TEMPLATE.format(
            titles=", ".join(prefs.target_titles),
            locations=", ".join(prefs.locations),
            seniority=prefs.seniority_level or "Any",
            job_types=", ".join(prefs.job_types) if prefs.job_types else "Any",
            industries=", ".join(prefs.industries) if prefs.industries else "Any",
            salary_line=salary_line,
        )

    async def _call_perplexity(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.settings.perplexity_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.perplexity_model,
            "messages": [{"role": "user", "content": prompt}],
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json=payload,
            )
        if resp.status_code >= 400:
            logger.error("Perplexity API error %s: %s", resp.status_code, resp.text)
            return "[]"
        content = resp.json()["choices"][0]["message"]["content"]
        return content

    def _parse_results(self, raw: str) -> list[dict[str, Any]]:
        match = re.search(r"\[.*]", raw, re.DOTALL)
        if not match:
            logger.warning("No JSON array found in Perplexity response")
            return []
        try:
            items = json.loads(match.group())
        except json.JSONDecodeError:
            logger.warning("Failed to parse Perplexity JSON response")
            return []

        jobs: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict) or not item.get("title"):
                continue
            description = item.get("description", "") or ""
            company = item.get("company") or None
            job = {
                "id": str(uuid4()),
                "source": "perplexity",
                "source_url": item.get("source_url") or f"https://search.perplexity.ai/{uuid4().hex[:8]}",
                "title": item["title"],
                "company": company,
                "location": item.get("location"),
                "description": description,
                "job_type": self._infer_job_type(
                    item.get("job_type", ""), description
                ),
                "agency": detect_agency(company=company, description=description),
                "status": "NEW",
            }
            salary = self._parse_salary(item.get("salary_text", ""))
            job.update(salary)
            jobs.append(job)
        return jobs

    @staticmethod
    def _infer_job_type(explicit: str, description: str) -> str | None:
        normalized = explicit.strip().upper()
        if normalized in ("PERM", "PERMANENT"):
            return "PERM"
        if normalized in ("CONTRACT", "FREELANCE", "FTC", "INTERIM"):
            return "CONTRACT"
        for jtype, pattern in _JOB_TYPE_PATTERNS.items():
            if pattern.search(description):
                return jtype
        return None

    @staticmethod
    def _parse_salary(text: str) -> dict[str, int | None]:
        if not text:
            return {"salary_min": None, "salary_max": None}
        numbers = [int(n.replace(",", "")) for n in re.findall(r"[\d,]+", text)]
        numbers = [n for n in numbers if 10_000 <= n <= 1_000_000]
        if len(numbers) >= 2:
            return {"salary_min": min(numbers), "salary_max": max(numbers)}
        if len(numbers) == 1:
            return {"salary_min": numbers[0], "salary_max": None}
        return {"salary_min": None, "salary_max": None}
