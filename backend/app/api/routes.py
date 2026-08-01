from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from app.api.deps import get_repository
from app.core.config import Settings, get_settings
from app.models import (
    ApplicationStatus,
    ArtifactRegenerationRequest,
    ArtifactSaveRequest,
    JobDetail,
    JobSummary,
    JobType,
    Preferences,
    StatusUpdate,
)
from app.services.ai import ApplicationWriter
from app.services.scheduler import DiscoveryScheduler

router = APIRouter(prefix="/api")

Repo = Annotated[Any, Depends(get_repository)]


def get_writer() -> ApplicationWriter:
    return ApplicationWriter()


def _require_trigger_auth(
    settings: Settings,
    authorization: str | None,
) -> None:
    if not settings.trigger_token_configured:
        return
    expected = f"Bearer {settings.pipeline_trigger_token}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing pipeline trigger token",
        )


def _get_scheduler(request: Request) -> DiscoveryScheduler:
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler is not available",
        )
    return scheduler


@router.get("/health")
async def health(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    db_configured = settings.supabase_configured or getattr(
        settings, "database_configured", False
    )
    scheduler = getattr(request.app.state, "scheduler", None)
    payload: dict[str, object] = {
        "status": "ok",
        "environment": settings.app_env,
        "data_store": (
            "supabase"
            if settings.supabase_configured
            else (
                "postgres"
                if getattr(settings, "database_configured", False)
                else "local"
            )
        ),
        "supabase_configured": settings.supabase_configured,
        "database_configured": getattr(settings, "database_configured", False),
        "anthropic_configured": settings.anthropic_configured,
        "perplexity_configured": settings.perplexity_configured,
        "scheduler_enabled": settings.scheduler_enabled,
        "discovery_schedule_mode": settings.discovery_schedule_mode,
        "discovery_times": settings.discovery_time_list,
        "discovery_timezone": settings.discovery_timezone,
        "ready_for_discovery": bool(
            settings.perplexity_configured
            and db_configured
            and settings.anthropic_configured
        ),
    }
    if scheduler is not None:
        payload["scheduler"] = scheduler.status()
    return payload


@router.get("/scheduler/status")
async def scheduler_status(request: Request) -> dict[str, object]:
    return _get_scheduler(request).status()


@router.post("/pipeline/run")
async def run_pipeline(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    """Trigger one discovery cycle. Used by cron, VPS, and Cursor automations."""
    _require_trigger_auth(settings, authorization)
    scheduler = _get_scheduler(request)
    result = await scheduler.run_once(trigger="api")
    if result.get("status") == "rejected":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result)
    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result,
        )
    return result


@router.get("/jobs", response_model=list[JobSummary])
async def list_jobs(
    repository: Repo,
    status_filter: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
    job_type: JobType | None = None,
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    max_score: Annotated[int | None, Query(ge=0, le=100)] = None,
) -> list[JobSummary]:
    return await repository.list_jobs(status_filter, job_type, min_score, max_score)


@router.get("/jobs/{job_id}", response_model=JobDetail)
async def get_job(job_id: UUID, repository: Repo) -> JobDetail:
    return await repository.get_job(job_id)


@router.patch("/jobs/{job_id}/status", response_model=JobDetail)
async def update_status(job_id: UUID, request: StatusUpdate, repository: Repo) -> JobDetail:
    return await repository.update_status(job_id, request.status)


@router.post("/jobs/{job_id}/regenerate", response_model=JobDetail)
async def regenerate_artifact(
    job_id: UUID,
    request: ArtifactRegenerationRequest,
    repository: Repo,
    writer: Annotated[ApplicationWriter, Depends(get_writer)],
) -> JobDetail:
    job = await repository.get_job(job_id)
    content = await writer.regenerate(job, request.artifact, request.notes)
    return await repository.save_artifact(job_id, request.artifact, content)


@router.patch("/jobs/{job_id}/artifacts", response_model=JobDetail)
async def save_artifact(job_id: UUID, request: ArtifactSaveRequest, repository: Repo) -> JobDetail:
    return await repository.save_artifact(job_id, request.artifact, request.content)


@router.get("/analytics")
async def get_analytics(repository: Repo) -> dict[str, object]:
    counts = await repository.get_status_counts()
    total = sum(counts.values())
    return {
        "total_jobs": total,
        "status_counts": counts,
        "submitted": counts.get("SUBMITTED", 0),
        "interviews": counts.get("INTERVIEW", 0),
        "offers": counts.get("OFFER", 0),
    }


@router.get("/preferences")
async def get_preferences(repository: Repo) -> dict[str, Preferences | None]:
    return {"preferences": await repository.get_preferences()}


@router.put("/preferences", response_model=Preferences)
async def save_preferences(preferences: Preferences, repository: Repo) -> Preferences:
    return await repository.save_preferences(preferences)
