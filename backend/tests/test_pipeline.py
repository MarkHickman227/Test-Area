from uuid import UUID

import pytest

from app.models import CvRecord, Preferences
from app.services.pipeline import Pipeline


JOB_ID = "11111111-1111-1111-1111-111111111111"


class FakePipelineRepository:
    def __init__(self):
        self.inserted_jobs = []
        self.updated_fields = {}
        self.inserted_artifacts = []
        self.inserted_outreach = []

    async def get_best_cv(self):
        return {
            "id": "22222222-2222-2222-2222-222222222222",
            "label": "EA",
            "parsed_profile": {"skills": ["architecture", "cloud", "strategy"]},
        }

    async def insert_job(self, job):
        self.inserted_jobs.append(job)
        return {**job, "id": JOB_ID}

    async def update_job_fields(self, job_id, fields):
        self.updated_fields.setdefault(job_id, {}).update(fields)

    async def insert_artifact(self, job_id, artifact_type, content):
        self.inserted_artifacts.append((job_id, artifact_type, content))

    async def insert_recruiter_outreach(self, job_id, email_body):
        self.inserted_outreach.append((job_id, email_body))


class FakeDiscoveryService:
    def __init__(self):
        self.jobs = [
            {
                "title": "Enterprise Architect",
                "company": "Acme Corp",
                "location": "London",
                "description": "Lead the architecture team.",
                "source_url": "https://example.com/j/1",
                "job_type": "PERM",
                "agency": False,
                "status": "NEW",
            }
        ]

    async def search_jobs(self, preferences):
        return self.jobs


class FakeEnrichmentService:
    async def extract_requirements(self, job):
        return {"required_skills": ["cloud", "strategy"], "seniority": "senior"}

    async def score_job(self, job, cv_profile, preferences):
        return {"score": 85, "score_explanation": "Strong match on strategy."}


class FakeWriter:
    async def generate_artifacts(self, job):
        artifacts = {"cover_letter": "Dear Hiring Manager...", "cv_summary": "Experienced architect."}
        if job.get("agency"):
            artifacts["recruiter_outreach"] = "Hi, I saw your listing..."
        return artifacts


@pytest.mark.asyncio
async def test_pipeline_runs_full_cycle():
    settings = type("S", (), {})()
    pipeline = Pipeline.__new__(Pipeline)
    pipeline.settings = settings
    pipeline.discovery = FakeDiscoveryService()
    pipeline.enrichment = FakeEnrichmentService()
    pipeline.writer = FakeWriter()

    repo = FakePipelineRepository()
    prefs = Preferences(
        target_titles=["Enterprise Architect"],
        locations=["London"],
        salary_min=80000,
    )

    stats = await pipeline.run(repo, prefs)

    assert stats["discovered"] == 1
    assert stats["enriched"] == 1
    assert stats["scored"] == 1
    assert stats["generated"] == 1
    assert len(repo.inserted_jobs) == 1
    assert len(repo.inserted_artifacts) == 2
    assert JOB_ID in repo.updated_fields
    assert repo.updated_fields[JOB_ID]["score"] == 85


@pytest.mark.asyncio
async def test_pipeline_skips_low_score_jobs():
    settings = type("S", (), {})()
    pipeline = Pipeline.__new__(Pipeline)
    pipeline.settings = settings
    pipeline.discovery = FakeDiscoveryService()
    pipeline.writer = FakeWriter()

    class LowScorer:
        async def extract_requirements(self, job):
            return {"required_skills": ["niche"]}

        async def score_job(self, job, cv_profile, preferences):
            return {"score": 30, "score_explanation": "Poor match."}

    pipeline.enrichment = LowScorer()
    repo = FakePipelineRepository()
    prefs = Preferences(target_titles=["EA"], locations=["London"])

    stats = await pipeline.run(repo, prefs)

    assert stats["generated"] == 0
    assert len(repo.inserted_artifacts) == 0
