from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

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
from app.services.repository import SupabaseRepository

router = APIRouter(prefix="/api")


def get_repository() -> SupabaseRepository:
    try:
        return SupabaseRepository()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


def get_writer() -> ApplicationWriter:
    return ApplicationWriter()


@router.get("/health")
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, object]:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "supabase_configured": bool(settings.supabase_url and settings.supabase_service_key),
        "anthropic_configured": bool(settings.anthropic_api_key),
        "perplexity_configured": bool(settings.perplexity_api_key),
        "scheduler_enabled": settings.scheduler_enabled,
    }


@router.get("/jobs", response_model=list[JobSummary])
async def list_jobs(
    repository: Annotated[SupabaseRepository, Depends(get_repository)],
    status_filter: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
    job_type: JobType | None = None,
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    max_score: Annotated[int | None, Query(ge=0, le=100)] = None,
) -> list[JobSummary]:
    return await repository.list_jobs(status_filter, job_type, min_score, max_score)


@router.get("/jobs/{job_id}", response_model=JobDetail)
async def get_job(
    job_id: UUID,
    repository: Annotated[SupabaseRepository, Depends(get_repository)],
) -> JobDetail:
    return await repository.get_job(job_id)


@router.patch("/jobs/{job_id}/status", response_model=JobDetail)
async def update_status(
    job_id: UUID,
    request: StatusUpdate,
    repository: Annotated[SupabaseRepository, Depends(get_repository)],
) -> JobDetail:
    return await repository.update_status(job_id, request.status)


@router.post("/jobs/{job_id}/regenerate", response_model=JobDetail)
async def regenerate_artifact(
    job_id: UUID,
    request: ArtifactRegenerationRequest,
    repository: Annotated[SupabaseRepository, Depends(get_repository)],
    writer: Annotated[ApplicationWriter, Depends(get_writer)],
) -> JobDetail:
    job = await repository.get_job(job_id)
    content = await writer.regenerate(job, request.artifact, request.notes)
    return await repository.save_artifact(job_id, request.artifact, content)


@router.patch("/jobs/{job_id}/artifacts", response_model=JobDetail)
async def save_artifact(
    job_id: UUID,
    request: ArtifactSaveRequest,
    repository: Annotated[SupabaseRepository, Depends(get_repository)],
) -> JobDetail:
    return await repository.save_artifact(job_id, request.artifact, request.content)


@router.get("/preferences")
async def get_preferences(
    repository: Annotated[SupabaseRepository, Depends(get_repository)],
) -> dict[str, Preferences | None]:
    return {"preferences": await repository.get_preferences()}


@router.put("/preferences", response_model=Preferences)
async def save_preferences(
    preferences: Preferences,
    repository: Annotated[SupabaseRepository, Depends(get_repository)],
) -> Preferences:
    return await repository.save_preferences(preferences)
