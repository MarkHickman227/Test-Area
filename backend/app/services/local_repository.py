"""In-memory repository with JSON file persistence for local development.

Falls back automatically when Supabase is not configured, enabling full
dashboard testing without any external services.
"""

import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.models import (
    ApplicationStatus,
    CvRecord,
    JobDetail,
    JobSummary,
    JobType,
    Preferences,
)

logger = logging.getLogger(__name__)

_DATA_FILE = Path("config/local_data.json")


class LocalRepository:
    """Dict-backed repository that persists to a JSON file."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {"jobs": {}, "artifacts": {}, "outreach": {}, "preferences": None, "cvs": {}}
        self._load()

    # ── jobs ────────────────────────────────────────────────────────

    async def list_jobs(
        self,
        status_filter: ApplicationStatus | None = None,
        job_type: JobType | None = None,
        min_score: int | None = None,
        max_score: int | None = None,
    ) -> list[JobSummary]:
        results = []
        for job in self._data["jobs"].values():
            if status_filter and job.get("status") != status_filter.value:
                continue
            if job_type and job.get("job_type") != job_type.value:
                continue
            if min_score is not None and (job.get("score") or 0) < min_score:
                continue
            if max_score is not None and (job.get("score") or 0) > max_score:
                continue
            results.append(JobSummary.model_validate(job))
        results.sort(key=lambda j: (-(j.score or 0), j.created_at or datetime.min), reverse=False)
        return results

    async def get_job(self, job_id: UUID) -> JobDetail:
        job = self._data["jobs"].get(str(job_id))
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        merged = dict(job)
        for art in self._data["artifacts"].get(str(job_id), []):
            self._merge_artifact(merged, art)
        outreach = self._data["outreach"].get(str(job_id))
        if outreach:
            merged["recruiter_outreach"] = outreach
        return JobDetail.model_validate(merged)

    async def update_status(self, job_id: UUID, new_status: ApplicationStatus) -> JobDetail:
        job = self._data["jobs"].get(str(job_id))
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        job["status"] = new_status.value
        self._save()
        return await self.get_job(job_id)

    async def save_artifact(self, job_id: UUID, artifact_type: str, content: Any) -> JobDetail:
        sid = str(job_id)
        if artifact_type == "screening_answers" and isinstance(content, str):
            content = [{"question": "Edited screening answers", "answer": content}]
        self._data["artifacts"].setdefault(sid, []).append(
            {"artifact_type": artifact_type, "content": content, "created_at": _now_str()}
        )
        if sid in self._data["jobs"]:
            self._data["jobs"][sid]["status"] = ApplicationStatus.draft.value
        self._save()
        return await self.get_job(job_id)

    # ── pipeline support ────────────────────────────────────────────

    async def insert_job(self, job: dict[str, Any]) -> dict[str, Any] | None:
        jid = job.get("id") or str(uuid4())
        url = job.get("source_url", "")
        for existing in self._data["jobs"].values():
            if existing.get("source_url") == url:
                return None
        row = {**job, "id": jid, "created_at": job.get("created_at") or _now_str()}
        self._data["jobs"][jid] = row
        self._save()
        return row

    async def update_job_fields(self, job_id: str, fields: dict[str, Any]) -> None:
        if job_id in self._data["jobs"]:
            self._data["jobs"][job_id].update(fields)
            self._save()

    async def insert_artifact(self, job_id: str, artifact_type: str, content: Any) -> None:
        self._data["artifacts"].setdefault(job_id, []).append(
            {"artifact_type": artifact_type, "content": content, "created_at": _now_str()}
        )
        self._save()

    async def insert_recruiter_outreach(self, job_id: str, email_body: str) -> None:
        self._data["outreach"][job_id] = {"email_body": email_body, "email_sent": False, "linkedin_sent": False}
        self._save()

    async def get_best_cv(self) -> dict[str, Any] | None:
        cvs = list(self._data["cvs"].values())
        if not cvs:
            return None
        cvs.sort(key=lambda cv: cv.get("created_at") or "", reverse=True)
        return cvs[0]

    async def list_pending_jobs(self, limit: int = 15) -> list[dict[str, Any]]:
        pending = []
        for job in self._data["jobs"].values():
            if job.get("status") != "NEW":
                continue
            score = job.get("score")
            if score is not None and int(score) >= 60:
                continue
            pending.append(job)
        pending.sort(key=lambda job: job.get("created_at") or "", reverse=True)
        return pending[:limit]

    # ── preferences ─────────────────────────────────────────────────

    async def get_preferences(self) -> Preferences | None:
        p = self._data.get("preferences")
        return Preferences.model_validate(p) if p else None

    async def save_preferences(self, preferences: Preferences) -> Preferences:
        self._data["preferences"] = preferences.model_dump(mode="json")
        self._save()
        return preferences

    # ── CVs ─────────────────────────────────────────────────────────

    async def list_cvs(self) -> list[CvRecord]:
        cvs = sorted(
            self._data["cvs"].values(),
            key=lambda cv: cv.get("created_at") or "",
            reverse=True,
        )
        return [CvRecord.model_validate(c) for c in cvs]

    async def create_cv(self, data: dict[str, Any]) -> CvRecord:
        cid = str(uuid4())
        row = {**data, "id": cid, "created_at": _now_str()}
        self._data["cvs"][cid] = row
        self._save()
        return CvRecord.model_validate(row)

    async def update_cv_profile(self, cv_id: UUID, parsed_profile: dict[str, Any]) -> CvRecord:
        row = self._data["cvs"].get(str(cv_id))
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found")
        row["parsed_profile"] = parsed_profile or {}
        self._save()
        return CvRecord.model_validate(row)

    async def delete_cv(self, cv_id: UUID) -> None:
        self._data["cvs"].pop(str(cv_id), None)
        self._save()

    # ── analytics ───────────────────────────────────────────────────

    async def get_status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for job in self._data["jobs"].values():
            s = job.get("status", "UNKNOWN")
            counts[s] = counts.get(s, 0) + 1
        return counts

    async def get_job_type_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for job in self._data["jobs"].values():
            key = job.get("job_type") or "UNKNOWN"
            counts[key] = counts.get(key, 0) + 1
        return counts

    async def get_submitted_job_type_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for job in self._data["jobs"].values():
            if job.get("status") not in {"SUBMITTED", "INTERVIEW", "OFFER"}:
                continue
            key = job.get("job_type") or "UNKNOWN"
            counts[key] = counts.get(key, 0) + 1
        return counts

    # ── persistence ─────────────────────────────────────────────────

    def _load(self) -> None:
        if _DATA_FILE.exists():
            try:
                self._data = json.loads(_DATA_FILE.read_text())
                logger.info("Loaded local data from %s", _DATA_FILE)
            except (json.JSONDecodeError, KeyError):
                logger.warning("Corrupt local data file, starting fresh")

    def _save(self) -> None:
        _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        _DATA_FILE.write_text(json.dumps(self._data, indent=2, default=str))

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


def _now_str() -> str:
    return datetime.now(timezone.utc).isoformat()
