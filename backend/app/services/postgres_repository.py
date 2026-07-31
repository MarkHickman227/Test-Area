from typing import Any
from uuid import UUID

import psycopg
from fastapi import HTTPException, status
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.core.config import Settings, get_settings
from app.models import ApplicationStatus, JobDetail, JobSummary, JobType, Preferences


class PostgresRepository:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.database_configured:
            raise RuntimeError("DATABASE_URL is required")

    async def list_jobs(
        self,
        status_filter: ApplicationStatus | None = None,
        job_type: JobType | None = None,
        min_score: int | None = None,
        max_score: int | None = None,
    ) -> list[JobSummary]:
        conditions: list[str] = []
        params: list[Any] = []
        if status_filter:
            conditions.append("status = %s")
            params.append(status_filter.value)
        if job_type:
            conditions.append("job_type = %s")
            params.append(job_type.value)
        if min_score is not None:
            conditions.append("score >= %s")
            params.append(min_score)
        if max_score is not None:
            conditions.append("score <= %s")
            params.append(max_score)

        where = f"where {' and '.join(conditions)}" if conditions else ""
        rows = await self._fetch_all(
            f"""
            select id, title, company, location, job_type, agency, score, status, source_url, created_at
            from jobs
            {where}
            order by score desc nulls last, created_at desc
            """,
            params,
        )
        return [JobSummary.model_validate(row) for row in rows]

    async def get_job(self, job_id: UUID) -> JobDetail:
        rows = await self._fetch_all("select * from jobs where id = %s limit 1", [job_id])
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

        job = dict(rows[0])
        artifacts = await self._fetch_all(
            """
            select artifact_type, content, cv_label, created_at
            from application_artifacts
            where job_id = %s
            order by created_at desc
            """,
            [job_id],
        )
        outreach = await self._fetch_all(
            "select * from recruiter_outreach where job_id = %s limit 1",
            [job_id],
        )

        for artifact in reversed(artifacts):
            self._merge_artifact(job, artifact)
        if outreach:
            job["recruiter_outreach"] = outreach[0]
        return JobDetail.model_validate(job)

    async def update_status(self, job_id: UUID, new_status: ApplicationStatus) -> JobDetail:
        await self._execute(
            "update jobs set status = %s where id = %s",
            [new_status.value, job_id],
        )
        return await self.get_job(job_id)

    async def save_artifact(self, job_id: UUID, artifact_type: str, content: Any) -> JobDetail:
        if artifact_type == "screening_answers" and isinstance(content, str):
            content = [{"question": "Edited screening answers", "answer": content}]
        await self._execute(
            """
            insert into application_artifacts (job_id, artifact_type, content)
            values (%s, %s, %s)
            """,
            [job_id, artifact_type, Jsonb(content)],
        )
        await self._execute(
            "update jobs set status = %s where id = %s",
            [ApplicationStatus.draft.value, job_id],
        )
        return await self.get_job(job_id)

    async def get_preferences(self) -> Preferences | None:
        rows = await self._fetch_all(
            "select * from user_preferences order by updated_at desc limit 1",
            [],
        )
        return Preferences.model_validate(rows[0]) if rows else None

    async def save_preferences(self, preferences: Preferences) -> Preferences:
        payload = preferences.model_dump(mode="json")
        await self._execute(
            """
            insert into user_preferences (
                target_titles, locations, salary_min, salary_max, job_types, industries, seniority_level
            )
            values (%s, %s, %s, %s, %s, %s, %s)
            """,
            [
                payload["target_titles"],
                payload["locations"],
                payload["salary_min"],
                payload["salary_max"],
                payload["job_types"],
                payload["industries"],
                payload["seniority_level"],
            ],
        )
        return preferences

    async def insert_job(self, job: dict[str, Any]) -> dict[str, Any] | None:
        columns = [
            "source",
            "source_url",
            "title",
            "company",
            "location",
            "description",
            "salary_min",
            "salary_max",
            "job_type",
            "agency",
            "parsed_requirements",
            "score",
            "score_explanation",
            "status",
        ]
        values: list[Any] = []
        placeholders: list[str] = []
        insert_cols: list[str] = []
        for column in columns:
            if column not in job:
                continue
            insert_cols.append(column)
            placeholders.append("%s")
            value = job[column]
            if column == "parsed_requirements":
                values.append(Jsonb(value if value is not None else {}))
            else:
                values.append(value)

        if "id" in job and job["id"]:
            insert_cols.insert(0, "id")
            placeholders.insert(0, "%s")
            values.insert(0, job["id"])

        query = f"""
            insert into jobs ({', '.join(insert_cols)})
            values ({', '.join(placeholders)})
            on conflict (source_url) do nothing
            returning *
        """
        rows = await self._fetch_all(query, values)
        return dict(rows[0]) if rows else None

    async def update_job_fields(self, job_id: str, fields: dict[str, Any]) -> None:
        if not fields:
            return
        assignments: list[str] = []
        params: list[Any] = []
        for key, value in fields.items():
            assignments.append(f"{key} = %s")
            if key in {"parsed_requirements"} or isinstance(value, (dict, list)):
                params.append(Jsonb(value))
            else:
                params.append(value)
        params.append(job_id)
        await self._execute(
            f"update jobs set {', '.join(assignments)}, updated_at = now() where id = %s",
            params,
        )

    async def insert_artifact(self, job_id: str, artifact_type: str, content: Any) -> None:
        await self._execute(
            """
            insert into application_artifacts (job_id, artifact_type, content)
            values (%s, %s, %s)
            """,
            [job_id, artifact_type, Jsonb(content)],
        )

    async def insert_recruiter_outreach(self, job_id: str, email_body: str) -> None:
        await self._execute(
            """
            insert into recruiter_outreach (job_id, email_body)
            values (%s, %s)
            on conflict (job_id) do update set email_body = excluded.email_body, updated_at = now()
            """,
            [job_id, email_body],
        )

    async def get_best_cv(self) -> dict[str, Any] | None:
        rows = await self._fetch_all(
            "select id, label, parsed_profile from cvs order by created_at desc limit 1",
            [],
        )
        return dict(rows[0]) if rows else None

    async def list_cvs(self):
        from app.models import CvRecord

        rows = await self._fetch_all("select * from cvs order by created_at desc", [])
        return [CvRecord.model_validate(row) for row in rows]

    async def create_cv(self, data: dict[str, Any]):
        from app.models import CvRecord

        rows = await self._fetch_all(
            """
            insert into cvs (label, file_name, raw_text, parsed_profile)
            values (%s, %s, %s, %s)
            returning *
            """,
            [
                data["label"],
                data["file_name"],
                data["raw_text"],
                Jsonb(data.get("parsed_profile") or {}),
            ],
        )
        return CvRecord.model_validate(rows[0])

    async def delete_cv(self, cv_id: UUID) -> None:
        await self._execute("delete from cvs where id = %s", [cv_id])

    async def get_status_counts(self) -> dict[str, int]:
        rows = await self._fetch_all("select status, count(*) as count from jobs group by status", [])
        return {row["status"]: int(row["count"]) for row in rows}

    async def _fetch_all(self, query: str, params: list[Any]) -> list[dict[str, Any]]:
        async with await psycopg.AsyncConnection.connect(
            self.settings.database_url,
            row_factory=dict_row,
        ) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                rows = await cursor.fetchall()
        return list(rows)

    async def _execute(self, query: str, params: list[Any]) -> None:
        async with await psycopg.AsyncConnection.connect(self.settings.database_url) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)

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
