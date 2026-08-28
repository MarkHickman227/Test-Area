from contextlib import ExitStack
from uuid import UUID

from fastapi.testclient import TestClient

from app.api.deps import get_repository
from app.api.routes import get_writer
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
        self.cvs: list = []

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

    async def get_status_counts(self):
        return {"DRAFT": 1}

    async def get_job_type_counts(self):
        return {"PERM": 1}

    async def get_submitted_job_type_counts(self):
        return {}

    async def list_cvs(self):
        return self.cvs

    async def create_cv(self, data):
        from uuid import uuid4

        from app.models import CvRecord

        self.created_cv = data
        record = CvRecord(
            id=uuid4(),
            label=data["label"],
            file_name=data["file_name"],
            raw_text=data["raw_text"],
            parsed_profile=data.get("parsed_profile") or {},
        )
        self.cvs.append(record)
        return record

    async def update_cv_profile(self, cv_id, parsed_profile):
        for cv in self.cvs:
            if cv.id == cv_id:
                cv.parsed_profile = parsed_profile or {}
                return cv
        raise AssertionError("CV not found")


class FakeWriter:
    async def regenerate(self, job, artifact, notes=None):
        return f"Regenerated {artifact} for {job.title}"


def make_client():
    app = create_app()
    repository = FakeRepository()
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_writer] = lambda: FakeWriter()
    stack = ExitStack()
    client = stack.enter_context(TestClient(app))
    client._applypilot_stack = stack  # keep lifespan alive for the test
    return client, repository



def test_root_serves_dashboard():
    client, _ = make_client()

    response = client.get("/")

    assert response.status_code == 200
    assert "ApplyPilot" in response.text
    assert "Job application review dashboard" in response.text


def test_health_reports_configuration_state():
    client, _ = make_client()

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "supabase_configured" in body
    assert body["discovery_schedule_mode"] == "twice_daily"
    assert body["discovery_times"] == ["08:00", "20:00"]
    assert body["repair_version"] == "cv-match-2"


def test_pipeline_run_skips_without_credentials():
    client, _ = make_client()

    response = client.post("/api/pipeline/run")

    assert response.status_code == 200
    assert response.json()["status"] == "skipped"


def test_pipeline_backfill_skips_without_credentials():
    client, _ = make_client()

    response = client.post("/api/pipeline/backfill")

    assert response.status_code == 200
    assert response.json()["status"] == "skipped"


def test_scheduler_status_endpoint():
    client, _ = make_client()

    response = client.get("/api/scheduler/status")

    assert response.status_code == 200
    assert response.json()["mode"] == "twice_daily"


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


def test_analytics_returns_status_counts():
    client, _ = make_client()

    response = client.get("/api/analytics")

    assert response.status_code == 200
    data = response.json()
    assert data["total_jobs"] == 1
    assert data["status_counts"]["DRAFT"] == 1
    assert data["job_type_counts"]["PERM"] == 1
    assert data["submitted_by_type"] == {}
    assert data["score_ge_60"] == 1
    assert data["draft_ready"] == 1
    assert data["max_score"] == 86
    assert data["unscored"] == 0


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


def test_create_cv_parses_profile():
    client, repository = make_client()

    response = client.post(
        "/api/cvs",
        json={
            "label": "Current",
            "file_name": "CV_current.docx",
            "raw_text": "Enterprise Architect with Azure, AWS, TOGAF and 20 years of contract delivery.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert "Azure" in body["parsed_profile"]["skills"]
    assert repository.created_cv["parsed_profile"]["contract_delivery_years"] == 20
    assert "open_to_contract" not in repository.created_cv["parsed_profile"]


def test_reparse_cvs_rebuilds_profile():
    client, repository = make_client()
    created = client.post(
        "/api/cvs",
        json={
            "label": "Current",
            "file_name": "CV_current.docx",
            "raw_text": "Enterprise Architect with Azure and TOGAF.",
        },
    )
    assert created.status_code == 201
    repository.cvs[0].parsed_profile = {}

    response = client.post("/api/cvs/reparse")

    assert response.status_code == 200
    body = response.json()
    assert "Azure" in body[0]["parsed_profile"]["skills"]
