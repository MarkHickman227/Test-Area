"""Authenticated image generation wrapper used by the HotAPI-backed path."""

from __future__ import annotations

import base64
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.crypto import get_crypto
from app.db import get_db
from app.deps import AuthContext, get_job_service, get_storage, require_auth
from app.errors import AppError
from app.jobs.runner import process_job_by_id
from app.models.enums import JobStatus, ModerationState
from app.models.generation import GenerationOutput
from app.routers.generations import to_view
from app.schemas.generation import GenerateImageRequest, GenerateImageResponse
from app.services.access import assert_country_allowed, check_rate_limit, request_country
from app.services.jobs import JobService
from app.services.pricing import ASPECT_TO_RESOLUTION

router = APIRouter(prefix="/v1", tags=["generations"])

SIZE_MAP = {
    "768x768": ("1:1", "768x768"),
    "1024x1024": ("1:1", "1024x1024"),
    "768x1152": ("2:3", "768x1152"),
    "1152x768": ("3:2", "1152x768"),
}


@router.post("/generate-image", response_model=GenerateImageResponse)
def generate_image(
    payload: GenerateImageRequest,
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
    size = payload.size.lower().replace(" ", "")
    mapped = SIZE_MAP.get(size)
    if not mapped or mapped not in ASPECT_TO_RESOLUTION:
        raise AppError("INVALID_OPTIONS", "Size is not allowed.", 400)
    aspect, resolution = mapped
    quality = payload.quality.lower().strip()
    if quality not in {"low", "medium", "high"}:
        raise AppError("INVALID_OPTIONS", "Quality must be low, medium, or high.", 400)
    job = jobs.create(
        ctx.user,
        {
            "idempotency_key": uuid4().hex,
            "model_profile_id": "adult-illustration-v1",
            "style_preset_id": "cinematic-photo-v1",
            "prompt": payload.prompt,
            "negative_prompt": None,
            "aspect_ratio": aspect,
            "resolution": resolution,
            "image_count": 1,
            "quality": quality,
        },
        request_id=getattr(request.state, "request_id", None),
    )
    if (
        settings.job_execution == "inline"
        and job.status == JobStatus.QUEUED
        and job.moderation_state != ModerationState.PENDING_REVIEW
    ):
        process_job_by_id(db, settings, get_crypto(), storage, job.id)
        db.refresh(job)
    view = to_view(db, job)
    image_b64 = None
    image_url = None
    if view.output_ids:
        output_id = view.output_ids[0]
        image_url = f"/v1/library/outputs/{output_id}/thumbnail"
        output = db.get(GenerationOutput, output_id)
        if output:
            image_b64 = base64.b64encode(storage.get(output.original_storage_key)).decode()
    return GenerateImageResponse(
        job_id=view.job_id,
        status=view.status,
        worker_id=view.worker_id,
        output_ids=view.output_ids,
        image_url=image_url,
        image=image_b64,
    )
