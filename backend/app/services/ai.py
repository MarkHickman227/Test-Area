import logging
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import Settings, get_settings
from app.models import JobDetail

logger = logging.getLogger(__name__)


class ApplicationWriter:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def regenerate(self, job: JobDetail, artifact: str, notes: str | None = None) -> Any:
        if not self.settings.anthropic_configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ANTHROPIC_API_KEY is required to regenerate artifacts",
            )

        prompt = self._build_prompt(job, artifact, notes)
        return await self._call_anthropic(prompt)

    async def generate_artifacts(self, job: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.anthropic_configured:
            logger.info("Skipping artifact generation — ANTHROPIC_API_KEY not set")
            return {}

        artifacts: dict[str, Any] = {}
        for artifact_type in ("cover_letter", "cv_summary", "screening_answers"):
            prompt = self._build_pipeline_prompt(job, artifact_type)
            content = await self._call_anthropic(prompt)
            if content:
                artifacts[artifact_type] = content
        if job.get("agency"):
            prompt = self._build_pipeline_prompt(job, "recruiter_outreach")
            content = await self._call_anthropic(prompt)
            if content:
                artifacts["recruiter_outreach"] = content
        return artifacts

    async def _call_anthropic(self, prompt: str) -> str:
        payload = {
            "model": self.settings.anthropic_model,
            "max_tokens": 1800,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "x-api-key": self.settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            )
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)

        blocks = response.json().get("content", [])
        return "\n".join(block.get("text", "") for block in blocks if block.get("type") == "text")

    @staticmethod
    def _build_prompt(job: JobDetail, artifact: str, notes: str | None) -> str:
        guidance = _ARTIFACT_GUIDANCE[artifact]
        return (
            f"{guidance}\n\n"
            "Keep claims grounded in the supplied CV summary and job details. "
            "Do not invent experience or credentials.\n\n"
            f"Job title: {job.title}\n"
            f"Company: {job.company or 'Unknown'}\n"
            f"Location: {job.location or 'Unknown'}\n"
            f"Score explanation: {job.score_explanation or 'Not available'}\n"
            f"Parsed requirements: {job.parsed_requirements}\n"
            f"Existing CV summary: {job.tailored_summary or 'Not available'}\n"
            f"Job description:\n{job.description or 'Not available'}\n\n"
            f"Reviewer notes: {notes or 'None'}"
        )

    @staticmethod
    def _build_pipeline_prompt(job: dict[str, Any], artifact: str) -> str:
        guidance = _ARTIFACT_GUIDANCE[artifact]
        return (
            f"{guidance}\n\n"
            "Keep claims grounded in the job details. "
            "Do not invent experience or credentials.\n\n"
            f"Job title: {job.get('title', 'Unknown')}\n"
            f"Company: {job.get('company') or 'Unknown'}\n"
            f"Location: {job.get('location') or 'Unknown'}\n"
            f"Score explanation: {job.get('score_explanation') or 'Not available'}\n"
            f"Parsed requirements: {job.get('parsed_requirements', {})}\n"
            f"Job description:\n{job.get('description') or 'Not available'}"
        )


_ARTIFACT_GUIDANCE: dict[str, str] = {
    "cv_summary": "Write a concise tailored CV headline and profile summary.",
    "cover_letter": "Write a specific, human-editable cover letter for this role.",
    "screening_answers": "Draft likely screening question answers using the available role context.",
    "recruiter_outreach": "Draft a short recruiter outreach email for an agency-listed role.",
}
