from __future__ import annotations

import asyncio
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import AuthContext, get_job_service, get_storage, require_auth
from app.errors import AppError
from app.jobs.runner import process_job_by_id
from app.models.enums import JobStatus, ModerationState
from app.models.generation import GenerationJob, ModelProfile, StylePreset
from app.schemas.generation import (
    CancelResponse,
    CreateGenerationRequest,
    GenerationJobView,
    GenerationOptions,
    RerunRequest,
)
from app.services.jobs import JobService
from app.services.pricing import (
    ALLOWED_ASPECTS,
    ALLOWED_COUNTS,
    ALLOWED_RESOLUTIONS,
    PRICING_RULE_VERSION,
)
from app.crypto import get_crypto
from app.services.access import (
    assert_country_allowed,
    check_rate_limit,
    request_country,
)

router = APIRouter(prefix="/v1/generations", tags=["generations"])
options_router = APIRouter(prefix="/v1/generation", tags=["generations"])


def _queue_position(db: Session, job: GenerationJob) -> int | None:
    if job.status != JobStatus.QUEUED:
        return None
    ahead = db.scalar(
        select(func.count())
        .select_from(GenerationJob)
        .where(
            GenerationJob.status == JobStatus.QUEUED,
            GenerationJob.queued_at < (job.queued_at or job.submitted_at),
        )
    )
    return int(ahead or 0) + 1


def to_view(db: Session, job: GenerationJob) -> GenerationJobView:
    pos = _queue_position(db, job)
    reserved = (
        job.credit_cost
        if job.status
        in {
            JobStatus.QUEUED,
            JobStatus.RUNNING,
            JobStatus.POST_PROCESSING,
            JobStatus.COMPLETED,
            JobStatus.BLOCKED,
        }
        and job.reservation_ledger_event_id
        else 0
    )
    if job.status in {
        JobStatus.CANCELLED,
        JobStatus.FAILED,
        JobStatus.EXPIRED,
        JobStatus.BLOCKED,
    }:
        reserved = 0 if job.status != JobStatus.COMPLETED else job.credit_cost
    return GenerationJobView(
        job_id=job.id,
        status=job.status,
        estimated_credit_cost=job.credit_cost,
        credits_reserved=(
            job.credit_cost
            if job.reservation_ledger_event_id
            and job.status
            not in {
                JobStatus.CANCELLED,
                JobStatus.EXPIRED,
                JobStatus.FAILED,
                JobStatus.BLOCKED,
            }
            else 0
        ),
        queue_position=pos,
        estimated_start_seconds=(pos * 30 if pos else None),
        policy_decision=job.policy_decision,
        model_profile_id=job.model_profile_id,
        style_preset_id=job.style_preset_id,
        image_count=job.image_count,
        seed=job.seed,
        parameters=job.parameters,
        created_at=job.created_at,
        failure_code=job.failure_code,
        worker_id=job.worker_id,
    )


@options_router.get("/options", response_model=GenerationOptions)
def options(
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    profiles = db.scalars(
        select(ModelProfile).where(ModelProfile.active.is_(True))
    ).all()
    presets = db.scalars(select(StylePreset).where(StylePreset.active.is_(True))).all()
    return GenerationOptions(
        model_profiles=[
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "base_credit_cost": p.base_credit_cost,
                "resolutions": p.allowed_resolutions,
            }
            for p in profiles
        ],
        style_presets=[
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "model_profile_id": p.model_profile_id,
            }
            for p in presets
        ],
        aspect_ratios=ALLOWED_ASPECTS,
        resolutions=ALLOWED_RESOLUTIONS,
        image_counts=ALLOWED_COUNTS,
        pricing_rule_version=PRICING_RULE_VERSION,
        content_policy_version=settings.current_content_policy_version,
    )


@router.post("", response_model=GenerationJobView)
def create_job(
    payload: CreateGenerationRequest,
    request: Request,
    ctx: AuthContext = Depends(require_auth),
    jobs: JobService = Depends(get_job_service),
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
):
    settings = get_settings()
    assert_country_allowed(settings, request_country(request))
    check_rate_limit(
        f"generate:{ctx.user.id}",
        settings.generate_rate_limit_per_minute,
    )
    job = jobs.create(
        ctx.user,
        payload.model_dump(),
        request_id=getattr(request.state, "request_id", None),
    )
    settings = get_settings()
    if (
        settings.job_execution == "inline"
        and job.status == JobStatus.QUEUED
        and job.moderation_state != ModerationState.PENDING_REVIEW
    ):
        process_job_by_id(db, settings, get_crypto(), storage, job.id)
        db.refresh(job)
    return to_view(db, job)


@router.get("", response_model=list[GenerationJobView])
def list_jobs(
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(GenerationJob)
        .where(GenerationJob.user_id == ctx.user.id)
        .order_by(GenerationJob.created_at.desc())
        .limit(100)
    ).all()
    return [to_view(db, job) for job in rows]


@router.get("/{job_id}", response_model=GenerationJobView)
def get_job(
    job_id: str,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
):
    job = db.get(GenerationJob, job_id)
    if not job or job.user_id != ctx.user.id:
        raise AppError("JOB_NOT_FOUND", "Job not found.", 404)
    return to_view(db, job)


@router.post("/{job_id}/cancel", response_model=CancelResponse)
def cancel_job(
    job_id: str,
    ctx: AuthContext = Depends(require_auth),
    jobs: JobService = Depends(get_job_service),
):
    job = jobs.cancel(ctx.user, job_id)
    return CancelResponse(job_id=job.id, status=job.status)


@router.post("/{job_id}/rerun", response_model=GenerationJobView)
def rerun_job(
    job_id: str,
    payload: RerunRequest,
    ctx: AuthContext = Depends(require_auth),
    jobs: JobService = Depends(get_job_service),
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
):
    job = jobs.rerun(ctx.user, job_id, payload.idempotency_key)
    settings = get_settings()
    if settings.job_execution == "inline" and job.status == JobStatus.QUEUED:
        process_job_by_id(db, settings, get_crypto(), storage, job.id)
        db.refresh(job)
    return to_view(db, job)


@router.get("/{job_id}/events")
async def job_events(
    job_id: str,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
):
    job = db.get(GenerationJob, job_id)
    if not job or job.user_id != ctx.user.id:
        raise AppError("JOB_NOT_FOUND", "Job not found.", 404)

    async def stream():
        for _ in range(60):
            db.expire_all()
            current = db.get(GenerationJob, job_id)
            if not current:
                break
            yield f"data: {current.status}\n\n"
            if current.status in {
                JobStatus.COMPLETED,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
                JobStatus.BLOCKED,
                JobStatus.EXPIRED,
            }:
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream")
