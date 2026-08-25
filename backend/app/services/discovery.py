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

_STRONG_CONTRACT = re.compile(
    r"\b(?:freelance|ftc|fixed[\s-]?term|interim|c2c|"
    r"outside\s+ir35|inside\s+ir35|temporary|temp(?:\s*|-)?to(?:\s*|-)?perm|"
    r"project\s+basis|\d+\s*month(?:s)?\s+(?:ftc|contract|fixed)|"
    r"day\s*rate|per\s*day|p/?d)\b",
    re.IGNORECASE,
)
_GENERIC_CONTRACT = re.compile(r"\bcontract\b", re.IGNORECASE)
_STRONG_PERM = re.compile(r"\b(?:permanent|perm(?!\w)|salaried)\b", re.IGNORECASE)
_FULL_TIME = re.compile(r"\bfull[\s-]?time\b", re.IGNORECASE)
_DAY_RATE = re.compile(
    r"(?:£|gbp)?\s*(\d{2,4}(?:,\d{3})?)\s*(?:-|to|–)\s*(?:£|gbp)?\s*"
    r"(\d{2,4}(?:,\d{3})?)?\s*(?:per\s*day|/day|p/?d|a\s*day|day\s*rate)"
    r"|(?:£|gbp)?\s*(\d{2,4}(?:,\d{3})?)\s*(?:per\s*day|/day|p/?d|a\s*day|day\s*rate)",
    re.IGNORECASE,
)
WORKING_DAYS = 220

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
            day_rate = max(1, round(prefs.salary_min / WORKING_DAYS))
            salary_line = (
                f"- Minimum salary: £{prefs.salary_min:,} permanent, or about "
                f"£{day_rate:,}+ per day for CONTRACT / FTC / IR35 roles. "
                "Include day-rate contracts that meet that equivalent.\n"
            )
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
                    item.get("job_type"),
                    description,
                    title=item["title"],
                ),
                "agency": detect_agency(company=company, description=description),
                "status": "NEW",
            }
            salary = self._parse_salary(item.get("salary_text") or "")
            job.update(salary)
            jobs.append(job)
        return jobs

    @staticmethod
    def _infer_job_type(
        explicit: str | None,
        description: str | None = "",
        title: str | None = "",
    ) -> str | None:
        """Infer PERM vs CONTRACT. Full-time does not override a contract role."""
        title_text = title or ""
        cleaned_description = re.sub(
            r"contract\s*type\s*:\s*permanent",
            "permanent",
            description or "",
            flags=re.IGNORECASE,
        )
        haystack = f"{title_text}\n{cleaned_description}"

        if _STRONG_CONTRACT.search(title_text) or _GENERIC_CONTRACT.search(title_text):
            return "CONTRACT"
        if _STRONG_CONTRACT.search(cleaned_description):
            return "CONTRACT"
        if _GENERIC_CONTRACT.search(cleaned_description):
            if _STRONG_PERM.search(cleaned_description):
                return "PERM"
            return "CONTRACT"

        normalized = (explicit or "").strip().upper()
        if normalized in ("CONTRACT", "FREELANCE", "FTC", "INTERIM", "TEMPORARY"):
            return "CONTRACT"
        if normalized in ("PERM", "PERMANENT"):
            return "PERM"

        if _STRONG_PERM.search(haystack) or _FULL_TIME.search(haystack):
            return "PERM"
        return None

    @staticmethod
    def _parse_salary(text: str | None) -> dict[str, int | None]:
        if not text:
            return {"salary_min": None, "salary_max": None}
        day_match = _DAY_RATE.search(text)
        if day_match:
            day_rates = [
                int(value.replace(",", ""))
                for value in day_match.groups()
                if value
            ]
            day_rates = [rate for rate in day_rates if 150 <= rate <= 2500]
            if day_rates:
                annual = [rate * WORKING_DAYS for rate in day_rates]
                if len(annual) >= 2:
                    return {"salary_min": min(annual), "salary_max": max(annual)}
                return {"salary_min": annual[0], "salary_max": None}
        numbers = [
            int(n.replace(",", ""))
            for n in re.findall(r"\d[\d,]*", text)
            if n.replace(",", "").isdigit()
        ]
        numbers = [n for n in numbers if 10_000 <= n <= 1_000_000]
        if len(numbers) >= 2:
            return {"salary_min": min(numbers), "salary_max": max(numbers)}
        if len(numbers) == 1:
            return {"salary_min": numbers[0], "salary_max": None}
        return {"salary_min": None, "salary_max": None}
