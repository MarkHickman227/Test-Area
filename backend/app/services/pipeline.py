import logging
from typing import Any

from app.core.config import Settings
from app.models import Preferences
from app.services.ai import ApplicationWriter
from app.services.apply import auto_apply, build_application_pack
from app.services.cv_parser import profile_for_scoring
from app.services.discovery import DiscoveryService
from app.services.enrichment import EnrichmentService
from app.services.job_match import compact_profile
from app.services.repository import SupabaseRepository

logger = logging.getLogger(__name__)

SCORE_THRESHOLD = 60
BACKFILL_LIMIT = 40


class Pipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.discovery = DiscoveryService(settings)
        self.enrichment = EnrichmentService(settings)
        self.writer = ApplicationWriter(settings)

    async def run(self, repository: SupabaseRepository, preferences: Preferences) -> dict[str, int]:
        stats = _empty_stats()
        jobs = await self.discovery.search_jobs(preferences)
        stats["discovered"] = len(jobs)
        logger.info("Discovered %d jobs", len(jobs))

        for job_data in jobs:
            inserted = await repository.insert_job(job_data)
            if inserted:
                stats["inserted"] += 1

        await self._process_pending(repository, preferences, stats, BACKFILL_LIMIT)
        logger.info("Pipeline complete: %s", stats)
        return stats

    async def backfill(
        self,
        repository: SupabaseRepository,
        preferences: Preferences,
        limit: int = BACKFILL_LIMIT,
    ) -> dict[str, int]:
        stats = _empty_stats()
        await self._process_pending(repository, preferences, stats, limit)
        logger.info("Backfill complete: %s", stats)
        return stats

    async def _process_pending(
        self,
        repository: SupabaseRepository,
        preferences: Preferences,
        stats: dict[str, int],
        limit: int,
    ) -> None:
        cv_row = await repository.get_best_cv()
        cv_profile = profile_for_scoring(cv_row)
        if cv_row and cv_profile:
            await repository.update_cv_profile(cv_row["id"], compact_profile(cv_profile))
        if not cv_profile:
            logger.warning("No usable CV loaded — scoring and artifact generation will be skipped")

        pending = await repository.list_pending_jobs(limit)
        for job in pending:
            await self._enrich_and_score(
                repository, str(job["id"]), job, cv_profile, preferences, stats
            )
            stats["processed"] += 1

    async def _enrich_and_score(
        self,
        repository: SupabaseRepository,
        job_id: str,
        job: dict[str, Any],
        cv_profile: dict[str, Any] | None,
        preferences: Preferences,
        stats: dict[str, int],
    ) -> None:
        requirements = job.get("parsed_requirements") or {}
        if not requirements:
            requirements = await self.enrichment.extract_requirements(job)
            if requirements:
                await repository.update_job_fields(job_id, {"parsed_requirements": requirements})
                job["parsed_requirements"] = requirements
                stats["enriched"] += 1

        if not cv_profile:
            stats["skipped_no_cv"] += 1
            return

        prefs = preferences.model_dump(mode="json")
        if job.get("job_type") == "CONTRACT" and prefs.get("salary_min"):
            prefs["contract_day_rate_min"] = max(1, round(int(prefs["salary_min"]) / 220))
            prefs["salary_note"] = (
                "salary_min is annual. For CONTRACT roles, treat day rate x 220 "
                "working days as the equivalent. Do not penalise day-rate contracts."
            )

        score_result = await self.enrichment.score_job(job, cv_profile, prefs)
        score = score_result.get("score")
        if score is None:
            return

        await repository.update_job_fields(
            job_id,
            {
                "score": score,
                "score_explanation": score_result.get("score_explanation", ""),
            },
        )
        job.update(score_result)
        stats["scored"] += 1

        if score >= SCORE_THRESHOLD:
            try:
                await self._generate_and_apply(
                    repository, job_id, job, cv_profile, stats
                )
            except Exception:
                logger.exception("Application failed for job %s", job_id)

    async def _generate_and_apply(
        self,
        repository: SupabaseRepository,
        job_id: str,
        job: dict[str, Any],
        cv_profile: dict[str, Any] | None,
        stats: dict[str, int],
    ) -> None:
        artifacts = await self.writer.generate_artifacts(job, cv_profile)
        if not artifacts.get("cover_letter"):
            artifacts.update(build_application_pack(job, cv_profile))
        for artifact_type, content in artifacts.items():
            if artifact_type == "recruiter_outreach":
                await repository.insert_recruiter_outreach(job_id, content)
            else:
                await repository.insert_artifact(job_id, artifact_type, content)

        if not artifacts:
            return

        stats["generated"] += 1
        auto_apply_on = getattr(self.settings, "auto_apply", True)
        if auto_apply_on:
            result = await auto_apply(job, artifacts, cv_profile, self.settings)
            await repository.update_job_fields(
                job_id,
                {"status": "SUBMITTED", "submitted_at": _now()},
            )
            stats["applied"] += 1
            logger.info(
                "Applied to %s via %s", job.get("title"), result.get("channel")
            )
            return

        await repository.update_job_fields(job_id, {"status": "DRAFT"})
        logger.info("Generated %d artifacts for job %s", len(artifacts), job.get("title"))


def _empty_stats() -> dict[str, int]:
    return {
        "discovered": 0,
        "inserted": 0,
        "processed": 0,
        "enriched": 0,
        "scored": 0,
        "generated": 0,
        "applied": 0,
        "skipped_no_cv": 0,
    }


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
