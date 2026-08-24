from __future__ import annotations

from urllib.parse import unquote

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.crypto import get_crypto
from app.db import get_db
from app.deps import AuthContext, get_storage, require_auth
from app.errors import AppError
from app.models.base import utcnow
from app.models.generation import GenerationJob, GenerationOutput
from app.models.system import DeletionRequest
from app.schemas.library import (
    BulkDeleteRequest,
    DownloadUrlResponse,
    OutputDetail,
    OutputView,
    PatchOutputRequest,
)
from app.services.audit import write_audit
from app.services.storage import StorageBackend

router = APIRouter(prefix="/v1/library", tags=["library"])


def _owned_output(db: Session, user_id: str, output_id: str) -> GenerationOutput:
    output = db.get(GenerationOutput, output_id)
    if not output or output.user_id != user_id or output.deleted_at:
        raise AppError("OUTPUT_NOT_FOUND", "Output not found.", 404)
    return output


def to_view(output: GenerationOutput) -> OutputView:
    return OutputView(
        id=output.id,
        job_id=output.job_id,
        sequence_number=output.sequence_number,
        width=output.width,
        height=output.height,
        mime_type=output.mime_type,
        bytes=output.bytes,
        favourite=output.favourite,
        created_at=output.created_at,
        scan_status=output.output_scan_status,
        deleted=output.deleted_at is not None,
    )


@router.get("/outputs", response_model=list[OutputView])
def list_outputs(
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
    favourite: bool | None = None,
    model_profile_id: str | None = None,
    q: str | None = Query(default=None, max_length=200),
):
    stmt = select(GenerationOutput).where(
        GenerationOutput.user_id == ctx.user.id,
        GenerationOutput.deleted_at.is_(None),
    )
    if favourite is True:
        stmt = stmt.where(GenerationOutput.favourite.is_(True))
    rows = db.scalars(
        stmt.order_by(GenerationOutput.created_at.desc()).limit(200)
    ).all()
    crypto = get_crypto()
    if model_profile_id or q:
        filtered = []
        for output in rows:
            job = db.get(GenerationJob, output.job_id)
            if not job:
                continue
            if model_profile_id and job.model_profile_id != model_profile_id:
                continue
            if q:
                prompt = crypto.decrypt(job.prompt_encrypted) or ""
                if q.lower() not in prompt.lower():
                    continue
            filtered.append(output)
        rows = filtered
    return [to_view(o) for o in rows]


@router.get("/outputs/{output_id}/thumbnail")
def thumbnail(
    output_id: str,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
):
    output = _owned_output(db, ctx.user.id, output_id)
    data = storage.get(output.thumbnail_storage_key)
    return Response(content=data, media_type="image/png")


@router.get("/outputs/{output_id}", response_model=OutputDetail)
def output_detail(
    output_id: str,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
):
    output = _owned_output(db, ctx.user.id, output_id)
    job = db.get(GenerationJob, output.job_id)
    crypto = get_crypto()
    return OutputDetail(
        **to_view(output).model_dump(),
        model_profile_id=job.model_profile_id if job else None,
        style_preset_id=job.style_preset_id if job else None,
        prompt=crypto.decrypt(job.prompt_encrypted) if job else None,
        negative_prompt=crypto.decrypt(job.negative_prompt_encrypted) if job else None,
        seed=job.seed if job else None,
        parameters=job.parameters if job else None,
    )


@router.post("/outputs/{output_id}/download-url", response_model=DownloadUrlResponse)
def download_url(
    output_id: str,
    request: Request,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
    kind: str = "original",
):
    output = _owned_output(db, ctx.user.id, output_id)
    settings = get_settings()
    key = (
        output.original_storage_key
        if kind != "thumbnail"
        else output.thumbnail_storage_key
    )
    url = storage.presign(key, settings.signed_url_ttl_seconds)
    write_audit(
        db,
        action="library.download_url",
        target_type="generation_output",
        target_id=output.id,
        actor_user_id=ctx.user.id,
        request_id=getattr(request.state, "request_id", None),
        metadata={"kind": kind},
    )
    db.commit()
    return DownloadUrlResponse(
        url=url, expires_in=settings.signed_url_ttl_seconds, kind=kind
    )


@router.get("/files/{key:path}")
def proxied_file(
    key: str,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
):
    decoded = unquote(key)
    output = db.scalar(
        select(GenerationOutput).where(
            GenerationOutput.user_id == ctx.user.id,
            (GenerationOutput.original_storage_key == decoded)
            | (GenerationOutput.thumbnail_storage_key == decoded),
        )
    )
    if not output or output.deleted_at:
        raise AppError("FILE_NOT_FOUND", "File not found.", 404)
    data = storage.get(decoded)
    write_audit(
        db,
        action="library.download",
        target_type="generation_output",
        target_id=output.id,
        actor_user_id=ctx.user.id,
    )
    db.commit()
    return Response(content=data, media_type=output.mime_type)


@router.patch("/outputs/{output_id}", response_model=OutputView)
def patch_output(
    output_id: str,
    payload: PatchOutputRequest,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
):
    output = _owned_output(db, ctx.user.id, output_id)
    if payload.favourite is not None:
        output.favourite = payload.favourite
    db.commit()
    return to_view(output)


def _delete_output(
    db: Session, storage: StorageBackend, output: GenerationOutput
) -> None:
    storage.delete(output.original_storage_key)
    storage.delete(output.thumbnail_storage_key)
    output.deleted_at = utcnow()


@router.delete("/outputs/{output_id}")
def delete_output(
    output_id: str,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
):
    output = _owned_output(db, ctx.user.id, output_id)
    _delete_output(db, storage, output)
    req = DeletionRequest(
        user_id=ctx.user.id, scope="OUTPUT", status="COMPLETED", completed_at=utcnow()
    )
    db.add(req)
    write_audit(
        db,
        action="library.deleted",
        target_type="generation_output",
        target_id=output.id,
        actor_user_id=ctx.user.id,
        metadata={"deletion_request_id": req.id},
    )
    db.commit()
    return {"ok": True, "deletion_request_id": req.id}


@router.post("/bulk-delete")
def bulk_delete(
    payload: BulkDeleteRequest,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
):
    stmt = select(GenerationOutput).where(
        GenerationOutput.user_id == ctx.user.id,
        GenerationOutput.deleted_at.is_(None),
    )
    if not payload.delete_all:
        ids = payload.output_ids or []
        if not ids:
            raise AppError("INVALID_REQUEST", "Provide output_ids or delete_all.")
        stmt = stmt.where(GenerationOutput.id.in_(ids))
    rows = db.scalars(stmt).all()
    for output in rows:
        _delete_output(db, storage, output)
    req = DeletionRequest(
        user_id=ctx.user.id,
        scope="BULK_OUTPUT" if not payload.delete_all else "ALL_OUTPUTS",
        status="COMPLETED",
        completed_at=utcnow(),
    )
    db.add(req)
    write_audit(
        db,
        action="library.bulk_deleted",
        target_type="user",
        target_id=ctx.user.id,
        actor_user_id=ctx.user.id,
        metadata={"count": len(rows), "deletion_request_id": req.id},
    )
    db.commit()
    return {"ok": True, "deleted": len(rows), "deletion_request_id": req.id}
