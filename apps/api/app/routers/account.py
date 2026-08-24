from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.crypto import get_crypto
from app.db import get_db
from app.deps import AuthContext, get_storage, require_auth
from app.errors import AppError
from app.models.base import utcnow
from app.models.enums import UserStatus
from app.models.generation import GenerationJob, GenerationOutput
from app.models.moderation import Report
from app.models.system import DataExportRequest, DeletionRequest
from app.models.user import ConsentAcceptance, User
from app.schemas.account import AccountUpdateRequest, ReportRequest
from app.services.audit import write_audit
from app.services.credits import ledger_balance
from app.services.storage import StorageBackend
from sqlalchemy import select
import json

router = APIRouter(tags=["account"])


@router.post("/v1/reports")
def create_report(
    payload: ReportRequest,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
):
    if payload.job_id:
        job = db.get(GenerationJob, payload.job_id)
        if not job or job.user_id != ctx.user.id:
            raise AppError("JOB_NOT_FOUND", "Job not found.", 404)
    report = Report(
        reporter_user_id=ctx.user.id,
        job_id=payload.job_id,
        output_id=payload.output_id,
        category=payload.category,
        description=payload.description,
        status="OPEN",
    )
    db.add(report)
    write_audit(
        db,
        action="report.created",
        target_type="report",
        target_id=report.id,
        actor_user_id=ctx.user.id,
    )
    db.commit()
    return {"id": report.id, "status": report.status}


@router.get("/v1/account")
def get_account(
    ctx: AuthContext = Depends(require_auth), db: Session = Depends(get_db)
):
    consents = db.scalars(
        select(ConsentAcceptance).where(ConsentAcceptance.user_id == ctx.user.id)
    ).all()
    settings = get_settings()
    return {
        "id": ctx.user.id,
        "email": ctx.user.email,
        "status": ctx.user.status,
        "role": ctx.user.role,
        "display_name": ctx.user.display_name,
        "age_verification_status": ctx.user.age_verification_status,
        "balance": ledger_balance(db, ctx.user.id),
        "consents": [
            {
                "document_type": c.document_type,
                "version": c.version,
                "accepted_at": c.accepted_at,
            }
            for c in consents
        ],
        "policy_versions": {
            "terms": settings.current_terms_version,
            "privacy": settings.current_privacy_version,
            "content_policy": settings.current_content_policy_version,
            "age_policy": settings.current_age_policy_version,
        },
    }


@router.patch("/v1/account")
def patch_account(
    payload: AccountUpdateRequest,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
):
    if payload.display_name is not None:
        ctx.user.display_name = payload.display_name[:80]
    db.commit()
    return {"ok": True}


@router.post("/v1/account/export")
def export_account(
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
):
    crypto = get_crypto()
    jobs = db.scalars(
        select(GenerationJob).where(GenerationJob.user_id == ctx.user.id)
    ).all()
    outputs = db.scalars(
        select(GenerationOutput).where(GenerationOutput.user_id == ctx.user.id)
    ).all()
    payload = {
        "user": {"id": ctx.user.id, "email": ctx.user.email, "status": ctx.user.status},
        "jobs": [
            {
                "id": j.id,
                "status": j.status,
                "prompt": crypto.decrypt(j.prompt_encrypted),
                "created_at": j.created_at.isoformat(),
            }
            for j in jobs
        ],
        "outputs": [
            {"id": o.id, "job_id": o.job_id, "deleted": o.deleted_at is not None}
            for o in outputs
        ],
    }
    raw = json.dumps(payload, indent=2).encode()
    key = f"exports/{ctx.user.id}/{utcnow().strftime('%Y%m%dT%H%M%S')}.json"
    storage.put(key, raw, "application/json")
    req = DataExportRequest(
        user_id=ctx.user.id, status="COMPLETED", storage_key=key, completed_at=utcnow()
    )
    db.add(req)
    write_audit(
        db,
        action="account.exported",
        target_type="user",
        target_id=ctx.user.id,
        actor_user_id=ctx.user.id,
    )
    db.commit()
    return {
        "id": req.id,
        "status": req.status,
        "download_path": f"/v1/library/files/{key}",
    }


@router.post("/v1/account/delete")
def delete_account(
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
):
    outputs = db.scalars(
        select(GenerationOutput).where(
            GenerationOutput.user_id == ctx.user.id,
            GenerationOutput.deleted_at.is_(None),
        )
    ).all()
    for output in outputs:
        storage.delete(output.original_storage_key)
        storage.delete(output.thumbnail_storage_key)
        output.deleted_at = utcnow()
    ctx.user.status = UserStatus.DELETED
    ctx.user.deleted_at = utcnow()
    ctx.user.email = f"deleted+{ctx.user.id}@invalid.local"
    ctx.user.password_hash = None
    ctx.session.revoked_at = utcnow()
    req = DeletionRequest(
        user_id=ctx.user.id, scope="ACCOUNT", status="COMPLETED", completed_at=utcnow()
    )
    db.add(req)
    write_audit(
        db,
        action="account.deleted",
        target_type="user",
        target_id=ctx.user.id,
        actor_user_id=ctx.user.id,
        metadata={"deletion_request_id": req.id},
    )
    db.commit()
    return {"ok": True, "deletion_request_id": req.id}
