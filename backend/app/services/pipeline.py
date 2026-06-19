import logging
from typing import Any

from app.core.config import Settings
from app.models import Preferences
from app.services.ai import ApplicationWriter
from app.services.discovery import DiscoveryService
from app.services.enrichment import EnrichmentService
from app.services.repository import SupabaseRepository

logger = logging.getLogger(__name__)

SCORE_THRESHOLD = 60


class Pipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.discovery = DiscoveryService(settings)
        self.enrichment = EnrichmentService(settings)
        self.writer = ApplicationWriter(settings)

    async def run(self, repository: SupabaseRepository, preferences: Preferences) -> dict[str, int]:
        stats = {"discovered": 0, "enriched": 0, "scored": 0, "generated": 0}

        jobs = await self.discovery.search_jobs(preferences)
        stats["discovered"] = len(jobs)
        logger.info("Discovered %d jobs", len(jobs))

        cv = await repository.get_best_cv()
        cv_profile = cv.get("parsed_profile", {}) if cv else {}

        for job_data in jobs:
            inserted = await repository.insert_job(job_data)
            if not inserted:
                continue
            job_id = inserted["id"]

            await self._enrich_and_score(repository, job_id, inserted, cv_profile, preferences, stats)

        logger.info("Pipeline complete: %s", stats)
        return stats

    async def _enrich_and_score(
        self,
        repository: SupabaseRepository,
        job_id: str,
        job: dict[str, Any],
        cv_profile: dict[str, Any],
        preferences: Preferences,
        stats: dict[str, int],
    ) -> None:
        requirements = await self.enrichment.extract_requirements(job)
        if requirements:
            await repository.update_job_fields(job_id, {"parsed_requirements": requirements})
            job["parsed_requirements"] = requirements
            stats["enriched"] += 1

        score_result = await self.enrichment.score_job(
            job, cv_profile, preferences.model_dump(mode="json")
        )
        score = score_result.get("score")
        if score is not None:
            await repository.update_job_fields(job_id, {
                "score": score,
                "score_explanation": score_result.get("score_explanation", ""),
            })
            job.update(score_result)
            stats["scored"] += 1

        if score is not None and score >= SCORE_THRESHOLD:
            await self._generate_artifacts(repository, job_id, job, stats)

    async def _generate_artifacts(
        self,
        repository: SupabaseRepository,
        job_id: str,
        job: dict[str, Any],
        stats: dict[str, int],
    ) -> None:
        artifacts = await self.writer.generate_artifacts(job)
        for artifact_type, content in artifacts.items():
            if artifact_type == "recruiter_outreach":
                await repository.insert_recruiter_outreach(job_id, content)
            else:
                await repository.insert_artifact(job_id, artifact_type, content)

        if artifacts:
            await repository.update_job_fields(job_id, {"status": "DRAFT"})
            stats["generated"] += 1
            logger.info("Generated %d artifacts for job %s", len(artifacts), job.get("title"))
