from uuid import UUID

from fastapi.testclient import TestClient

from app.api.routes import get_repository, get_writer
from app.main import create_app
from app.models import ApplicationStatus, JobDetail, JobSummary, Preferences


JOB_ID = UUID("11111111-1111-1111-1111-111111111111")


class FakeRepository:
    def __init__(self) -> None:
        self.job = JobDetail(
            id=JOB_ID,
            title="Enterprise Architect",
            company="Avalon",
            location="London",
            job_type="PERM",
            agency=True,
            score=86,
            status="DRAFT",
            source_url="https://example.com/job",
            description="Lead architecture across the estate.",
            parsed_requirements={"required_skills": ["strategy", "cloud"]},
            score_explanation="Strong match on strategy and leadership.",
            cover_letter="Original cover letter",
        )
        self.preferences = None

    async def list_jobs(self, status_filter=None, job_type=None, min_score=None, max_score=None):
        return [
            JobSummary(
                **self.job.model_dump(
                    include={
                        "id",
                        "title",
                        "company",
                        "location",
                        "job_type",
                        "agency",
                        "score",
                        "status",
                        "source_url",
                        "created_at",
                    }
                )
            )
        ]

    async def get_job(self, job_id):
        assert job_id == JOB_ID
        return self.job

    async def update_status(self, job_id, new_status):
        assert job_id == JOB_ID
        self.job.status = new_status
        return self.job

    async def save_artifact(self, job_id, artifact_type, content):
        assert job_id == JOB_ID
        if artifact_type == "cover_letter":
            self.job.cover_letter = content
        self.job.status = ApplicationStatus.draft
        return self.job

    async def get_preferences(self):
        return self.preferences

    async def save_preferences(self, preferences):
        self.preferences = preferences
        return preferences


class FakeWriter:
    async def regenerate(self, job, artifact, notes=None):
        return f"Regenerated {artifact} for {job.title}"


def make_client():
    app = create_app()
    repository = FakeRepository()
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_writer] = lambda: FakeWriter()
    return TestClient(app), repository


def test_health_reports_configuration_state():
    client, _ = make_client()

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "supabase_configured" in response.json()


def test_review_workflow_updates_status_and_regenerates_artifact():
    client, repository = make_client()

    jobs_response = client.get("/api/jobs?status=DRAFT&job_type=PERM&min_score=80")
    assert jobs_response.status_code == 200
    assert jobs_response.json()[0]["score"] == 86

    status_response = client.patch(f"/api/jobs/{JOB_ID}/status", json={"status": "READY"})
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "READY"

    regenerate_response = client.post(
        f"/api/jobs/{JOB_ID}/regenerate",
        json={"artifact": "cover_letter", "notes": "Make it concise"},
    )
    assert regenerate_response.status_code == 200
    assert "Regenerated cover_letter" in regenerate_response.json()["cover_letter"]
    assert repository.job.status == ApplicationStatus.draft


def test_preferences_can_be_saved():
    client, _ = make_client()
    preferences = Preferences(
        target_titles=["Enterprise Architect"],
        locations=["London", "Remote"],
        salary_min=80000,
        salary_max=150000,
        job_types=["PERM", "CONTRACT"],
        industries=["Financial Services"],
        seniority_level="Director",
    )

    response = client.put("/api/preferences", json=preferences.model_dump(mode="json"))

    assert response.status_code == 200
    assert response.json()["target_titles"] == ["Enterprise Architect"]
