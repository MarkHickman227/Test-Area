import json
import logging
import re
from typing import Any

import httpx

from app.core.config import Settings
from app.services.job_match import match_job_to_cv

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = (
    "Analyse this job description and return ONLY a JSON object with these keys:\n"
    "- required_skills: list of must-have skills\n"
    "- nice_to_have_skills: list of nice-to-have skills\n"
    "- experience_years: integer or null\n"
    "- domain_knowledge: list of relevant domains\n"
    "- certifications: list of required/preferred certifications\n"
    "- seniority: one of junior/mid/senior/lead/director/executive or null\n"
    "- keywords: list of important keywords for matching\n\n"
    "Job title: {title}\nCompany: {company}\n\nDescription:\n{description}"
)


class EnrichmentService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def extract_requirements(self, job: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.anthropic_configured:
            logger.info("Skipping enrichment — ANTHROPIC_API_KEY not configured")
            return {}

        prompt = EXTRACT_PROMPT.format(
            title=_safe_text(job.get("title", "")),
            company=_safe_text(job.get("company", "Unknown")),
            description=_safe_text(job.get("description", "")),
        )
        return await self._call_anthropic_json(prompt)

    async def score_job(
        self,
        job: dict[str, Any],
        cv_profile: dict[str, Any],
        preferences: dict[str, Any],
    ) -> dict[str, Any]:
        # Numeric score comes from CV vs job text. Anthropic was returning 0-25
        # against an empty profile and blocking drafts for roles already in search.
        return match_job_to_cv(job, cv_profile, preferences)

    async def _call_anthropic_json(self, prompt: str) -> dict[str, Any]:
        headers = {
            "x-api-key": self.settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.settings.anthropic_model,
            "max_tokens": 1200,
            "messages": [{"role": "user", "content": prompt}],
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            )
        if resp.status_code >= 400:
            logger.error("Anthropic API error %s: %s", resp.status_code, resp.text)
            return {}

        blocks = resp.json().get("content", [])
        text = "\n".join(
            b.get("text", "") for b in blocks if b.get("type") == "text"
        )
        return _parse_json_block(text)


def _safe_text(value: Any) -> str:
    return str(value or "").replace("{", "(").replace("}", ")")


def _parse_json_block(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*}", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {}


def _clamp_score(value: Any) -> int | None:
    if value is None:
        return None
    try:
        score = int(value)
    except (ValueError, TypeError):
        return None
    return max(0, min(100, score))
