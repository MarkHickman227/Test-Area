import logging
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException, status

from app.core.config import Settings, get_settings
from app.models import ApplicationStatus, CvRecord, JobDetail, JobSummary, JobType, Preferences

logger = logging.getLogger(__name__)


class SupabaseRepository:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.supabase_configured:
            raise RuntimeError("Supabase URL and service role key are required")

    @property
    def headers(self) -> dict[str, str]:
        key = self.settings.supabase_service_key or ""
        return {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def list_jobs(
        self,
        status_filter: ApplicationStatus | None = None,
        job_type: JobType | None = None,
        min_score: int | None = None,
        max_score: int | None = None,
    ) -> list[JobSummary]:
        params = [
            (
                "select",
                "id,title,company,location,job_type,agency,score,status,"
                "source_url,created_at",
            ),
            ("order", "score.desc.nullslast,created_at.desc"),
        ]
        if status_filter:
            params.append(("status", f"eq.{status_filter.value}"))
        if job_type:
            params.append(("job_type", f"eq.{job_type.value}"))
        if min_score is not None:
            params.append(("score", f"gte.{min_score}"))
        if max_score is not None:
            params.append(("score", f"lte.{max_score}"))

        rows = await self._request("GET", "jobs", params=params)
        return [JobSummary.model_validate(row) for row in rows]

    async def get_job(self, job_id: UUID) -> JobDetail:
        rows = await self._request(
            "GET",
            "jobs",
            params={"id": f"eq.{job_id}", "select": "*", "limit": "1"},
        )
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

        job = dict(rows[0])
        artifacts = await self._request(
            "GET",
            "application_artifacts",
            params={
                "job_id": f"eq.{job_id}",
                "select": "artifact_type,content,cv_label,created_at",
                "order": "created_at.desc",
            },
        )
        outreach = await self._request(
            "GET",
            "recruiter_outreach",
            params={"job_id": f"eq.{job_id}", "select": "*", "limit": "1"},
        )

        for artifact in reversed(artifacts):
            self._merge_artifact(job, artifact)
        if outreach:
            job["recruiter_outreach"] = outreach[0]
        return JobDetail.model_validate(job)

    async def update_status(self, job_id: UUID, new_status: ApplicationStatus) -> JobDetail:
        await self._request(
            "PATCH",
            "jobs",
            params={"id": f"eq.{job_id}"},
            json={"status": new_status.value},
        )
        return await self.get_job(job_id)

    async def save_artifact(self, job_id: UUID, artifact_type: str, content: Any) -> JobDetail:
        if artifact_type == "screening_answers" and isinstance(content, str):
            content = [{"question": "Edited screening answers", "answer": content}]
        await self._request(
            "POST",
            "application_artifacts",
            json={"job_id": str(job_id), "artifact_type": artifact_type, "content": content},
        )
        await self._request(
            "PATCH",
            "jobs",
            params={"id": f"eq.{job_id}"},
            json={"status": ApplicationStatus.draft.value},
        )
        return await self.get_job(job_id)

    async def get_preferences(self) -> Preferences | None:
        rows = await self._request(
            "GET",
            "user_preferences",
            params={"select": "*", "order": "updated_at.desc", "limit": "1"},
        )
        if not rows:
            return None
        return Preferences.model_validate(rows[0])

    async def save_preferences(self, preferences: Preferences) -> Preferences:
        await self._request("POST", "user_preferences", json=preferences.model_dump(mode="json"))
        return preferences

    async def insert_job(self, job: dict[str, Any]) -> dict[str, Any] | None:
        headers = {**self.headers, "Prefer": "return=representation,resolution=ignore-duplicates"}
        url = f"{self.settings.supabase_rest_url}/jobs"
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, headers=headers, json=job)
        if resp.status_code >= 400:
            logger.warning("Failed to insert job %s: %s", job.get("title"), resp.text)
            return None
        rows = resp.json() if resp.content else []
        return rows[0] if rows else None

    async def update_job_fields(self, job_id: str, fields: dict[str, Any]) -> None:
        await self._request("PATCH", "jobs", params={"id": f"eq.{job_id}"}, json=fields)

    async def insert_artifact(self, job_id: str, artifact_type: str, content: Any) -> None:
        await self._request(
            "POST",
            "application_artifacts",
            json={"job_id": job_id, "artifact_type": artifact_type, "content": content},
        )

    async def insert_recruiter_outreach(self, job_id: str, email_body: str) -> None:
        headers = {**self.headers, "Prefer": "return=representation,resolution=ignore-duplicates"}
        url = f"{self.settings.supabase_rest_url}/recruiter_outreach"
        payload = {"job_id": job_id, "email_body": email_body}
        async with httpx.AsyncClient(timeout=20) as client:
            await client.post(url, headers=headers, json=payload)

    async def get_best_cv(self) -> dict[str, Any] | None:
        rows = await self._request(
            "GET",
            "cvs",
            params={"select": "id,label,parsed_profile,raw_text", "order": "created_at.desc", "limit": "1"},
        )
        return rows[0] if rows else None

    async def list_pending_jobs(self, limit: int = 15) -> list[dict[str, Any]]:
        rows = await self._request(
            "GET",
            "jobs",
            params={
                "select": "*",
                "status": "eq.NEW",
                "score": "is.null",
                "order": "created_at.desc",
                "limit": str(limit),
            },
        )
        return list(rows or [])

    async def list_cvs(self) -> list[CvRecord]:
        rows = await self._request(
            "GET", "cvs", params={"select": "*", "order": "created_at.desc"}
        )
        return [CvRecord.model_validate(r) for r in rows]

    async def create_cv(self, data: dict[str, Any]) -> CvRecord:
        rows = await self._request("POST", "cvs", json=data)
        return CvRecord.model_validate(rows[0])

    async def update_cv_profile(self, cv_id: UUID, parsed_profile: dict[str, Any]) -> CvRecord:
        rows = await self._request(
            "PATCH",
            "cvs",
            params={"id": f"eq.{cv_id}"},
            json={"parsed_profile": parsed_profile or {}},
        )
        if not rows:
            from fastapi import HTTPException, status

            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found")
        return CvRecord.model_validate(rows[0])

    async def delete_cv(self, cv_id: UUID) -> None:
        await self._request("DELETE", "cvs", params={"id": f"eq.{cv_id}"})

    async def get_status_counts(self) -> dict[str, int]:
        rows = await self._request(
            "GET", "jobs", params={"select": "status"}
        )
        counts: dict[str, int] = {}
        for row in rows:
            s = row.get("status", "UNKNOWN")
            counts[s] = counts.get(s, 0) + 1
        return counts

    async def get_job_type_counts(self) -> dict[str, int]:
        rows = await self._request("GET", "jobs", params={"select": "job_type"})
        counts: dict[str, int] = {}
        for row in rows:
            key = row.get("job_type") or "UNKNOWN"
            counts[key] = counts.get(key, 0) + 1
        return counts

    async def get_submitted_job_type_counts(self) -> dict[str, int]:
        rows = await self._request(
            "GET",
            "jobs",
            params={
                "select": "job_type,status",
                "status": "in.(SUBMITTED,INTERVIEW,OFFER)",
            },
        )
        counts: dict[str, int] = {}
        for row in rows:
            key = row.get("job_type") or "UNKNOWN"
            counts[key] = counts.get(key, 0) + 1
        return counts

    async def _request(
        self,
        method: str,
        table: str,
        params: Any | None = None,
        json: Any | None = None,
    ) -> Any:
        url = f"{self.settings.supabase_rest_url}/{table}"
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.request(
                method,
                url,
                headers=self.headers,
                params=params,
                json=json,
            )
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        if not response.content:
            return []
        return response.json()

    @staticmethod
    def _merge_artifact(job: dict[str, Any], artifact: dict[str, Any]) -> None:
        artifact_type = artifact["artifact_type"]
        content = artifact["content"]
        if artifact_type == "cv_summary":
            job["tailored_summary"] = content.get("summary") if isinstance(content, dict) else content
            job["selected_cv_label"] = artifact.get("cv_label")
        elif artifact_type == "cover_letter":
            job["cover_letter"] = content
        elif artifact_type == "screening_answers":
            job["screening_answers"] = content
