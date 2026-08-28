import pytest

from app.models import Preferences
from app.services.pipeline import Pipeline


JOB_ID = "11111111-1111-1111-1111-111111111111"


_MISSING = object()


class FakePipelineRepository:
    def __init__(self, cv=_MISSING, existing_jobs=None):
        self.cv = {
            "id": "22222222-2222-2222-2222-222222222222",
            "label": "EA",
            "raw_text": "Enterprise Architect with Azure, AWS, and TOGAF.",
            "parsed_profile": {"skills": ["architecture", "cloud", "strategy"]},
        } if cv is _MISSING else cv
        self.inserted_jobs = []
        self.updated_fields = {}
        self.inserted_artifacts = []
        self.inserted_outreach = []
        self.jobs = {job["id"]: job for job in (existing_jobs or [])}

    async def get_best_cv(self):
        return self.cv

    async def insert_job(self, job):
        self.inserted_jobs.append(job)
        row = {**job, "id": JOB_ID, "status": job.get("status") or "NEW"}
        self.jobs[JOB_ID] = row
        return row

    async def list_pending_jobs(self, limit=15):
        pending = []
        for job in self.jobs.values():
            if job.get("status") != "NEW":
                continue
            score = job.get("score")
            if score is not None and int(score) >= 60:
                continue
            pending.append(job)
        return pending[:limit]

    async def update_job_fields(self, job_id, fields):
        self.updated_fields.setdefault(job_id, {}).update(fields)
        if job_id in self.jobs:
            self.jobs[job_id].update(fields)

    async def insert_artifact(self, job_id, artifact_type, content):
        self.inserted_artifacts.append((job_id, artifact_type, content))

    async def insert_recruiter_outreach(self, job_id, email_body):
        self.inserted_outreach.append((job_id, email_body))


class FakeDiscoveryService:
    def __init__(self, jobs=None):
        self.jobs = jobs if jobs is not None else [
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
        assert cv_profile, "scorer must receive a usable CV profile"
        return {"score": 85, "score_explanation": "Strong match on strategy."}


class FakeWriter:
    async def generate_artifacts(self, job):
        artifacts = {"cover_letter": "Dear Hiring Manager...", "cv_summary": "Experienced architect."}
        if job.get("agency"):
            artifacts["recruiter_outreach"] = "Hi, I saw your listing..."
        return artifacts


def _pipeline(discovery=None, enrichment=None):
    pipeline = Pipeline.__new__(Pipeline)
    pipeline.settings = type("S", (), {})()
    pipeline.discovery = discovery or FakeDiscoveryService()
    pipeline.enrichment = enrichment or FakeEnrichmentService()
    pipeline.writer = FakeWriter()
    return pipeline


@pytest.mark.asyncio
async def test_pipeline_runs_full_cycle():
    pipeline = _pipeline()
    repo = FakePipelineRepository()
    prefs = Preferences(
        target_titles=["Enterprise Architect"],
        locations=["London"],
        salary_min=80000,
    )

    stats = await pipeline.run(repo, prefs)

    assert stats["discovered"] == 1
    assert stats["inserted"] == 1
    assert stats["processed"] == 1
    assert stats["enriched"] == 1
    assert stats["scored"] == 1
    assert stats["generated"] == 1
    assert len(repo.inserted_artifacts) == 2
    assert repo.updated_fields[JOB_ID]["score"] == 85


@pytest.mark.asyncio
async def test_pipeline_skips_low_score_jobs():
    class LowScorer:
        async def extract_requirements(self, job):
            return {"required_skills": ["niche"]}

        async def score_job(self, job, cv_profile, preferences):
            return {"score": 30, "score_explanation": "Poor match."}

    pipeline = _pipeline(enrichment=LowScorer())
    repo = FakePipelineRepository()
    prefs = Preferences(target_titles=["EA"], locations=["London"])

    stats = await pipeline.run(repo, prefs)

    assert stats["generated"] == 0
    assert len(repo.inserted_artifacts) == 0


@pytest.mark.asyncio
async def test_pipeline_skips_scoring_without_cv():
    pipeline = _pipeline()
    repo = FakePipelineRepository(cv=None)
    prefs = Preferences(target_titles=["EA"], locations=["London"])

    stats = await pipeline.run(repo, prefs)

    assert stats["skipped_no_cv"] == 1
    assert stats["scored"] == 0
    assert stats["generated"] == 0


@pytest.mark.asyncio
async def test_pipeline_backfills_existing_new_jobs():
    existing = {
        "id": JOB_ID,
        "title": "Solutions Architect 6 month contract",
        "job_type": "CONTRACT",
        "status": "NEW",
        "score": None,
        "source_url": "https://example.com/existing",
    }
    pipeline = _pipeline(discovery=FakeDiscoveryService(jobs=[]))
    repo = FakePipelineRepository(existing_jobs=[existing])
    prefs = Preferences(target_titles=["EA"], locations=["London"], salary_min=80000)

    stats = await pipeline.run(repo, prefs)

    assert stats["discovered"] == 0
    assert stats["inserted"] == 0
    assert stats["processed"] == 1
    assert stats["scored"] == 1
    assert stats["generated"] == 1
    assert repo.updated_fields[JOB_ID]["score"] == 85


@pytest.mark.asyncio
async def test_pipeline_rescores_existing_low_score():
    existing = {
        "id": JOB_ID,
        "title": "Enterprise Architect",
        "job_type": "PERM",
        "status": "NEW",
        "score": 25,
        "source_url": "https://example.com/already-scored-wrong",
    }
    pipeline = _pipeline(discovery=FakeDiscoveryService(jobs=[]))
    repo = FakePipelineRepository(existing_jobs=[existing])
    prefs = Preferences(target_titles=["EA"], locations=["London"])

    stats = await pipeline.run(repo, prefs)

    assert stats["processed"] == 1
    assert stats["scored"] == 1
    assert stats["generated"] == 1
    assert repo.updated_fields[JOB_ID]["score"] == 85


@pytest.mark.asyncio
async def test_pipeline_backfill_skips_discovery():
    existing = {
        "id": JOB_ID,
        "title": "Solutions Architect",
        "job_type": "CONTRACT",
        "status": "NEW",
        "score": 15,
        "source_url": "https://example.com/contract",
    }
    discovery = FakeDiscoveryService(jobs=[{"title": "should not be used"}])
    pipeline = _pipeline(discovery=discovery)
    repo = FakePipelineRepository(existing_jobs=[existing])
    prefs = Preferences(target_titles=["EA"], locations=["London"])

    stats = await pipeline.backfill(repo, prefs)

    assert stats["discovered"] == 0
    assert stats["inserted"] == 0
    assert stats["processed"] == 1
    assert stats["scored"] == 1
    assert repo.updated_fields[JOB_ID]["score"] == 85
