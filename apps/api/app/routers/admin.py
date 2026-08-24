from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crypto import get_crypto
from app.db import get_db
from app.deps import AuthContext, require_roles
from app.errors import AppError
from app.jobs.runner import process_job_by_id
from app.models.base import utcnow
from app.models.billing import CreditLedger
from app.models.enums import (
    JobStatus,
    LedgerEventType,
    ModerationState,
    UserRole,
    UserStatus,
)
from app.models.generation import GenerationJob, GenerationOutput
from app.models.moderation import EnforcementAction, Report
from app.models.system import BreakGlassAccess
from app.models.user import User
from app.schemas.account import (
    BreakGlassRequest,
    LedgerAdjustRequest,
    ModerationDecisionRequest,
)
from app.services.audit import write_audit
from app.services.credits import append_event, ledger_balance, reconcile_user
from app.config import get_settings
from app.crypto import CryptoService
from app.deps import get_storage

router = APIRouter(prefix="/v1/admin", tags=["admin"])


def _moderator(
    ctx: AuthContext = Depends(require_roles(UserRole.MODERATOR, UserRole.SUPER_ADMIN))
) -> AuthContext:
    return ctx


@router.get("/queue")
def queue(
    ctx: AuthContext = Depends(
        require_roles(UserRole.MODERATOR, UserRole.SYSTEM_ADMIN, UserRole.SUPER_ADMIN)
    ),
    db: Session = Depends(get_db),
):
    write_audit(
        db,
        action="admin.queue_viewed",
        target_type="system",
        actor_user_id=ctx.user.id,
        actor_role=ctx.user.role,
    )
    db.commit()
    counts = {}
    for status in JobStatus:
        counts[status.value] = int(
            db.scalar(
                select(func.count())
                .select_from(GenerationJob)
                .where(GenerationJob.status == status)
            )
            or 0
        )
    held = db.scalars(
        select(GenerationJob)
        .where(GenerationJob.moderation_state == ModerationState.PENDING_REVIEW)
        .order_by(GenerationJob.created_at.desc())
        .limit(100)
    ).all()
    return {
        "counts": counts,
        "held_jobs": [
            {
                "id": j.id,
                "user_id": j.user_id,
                "status": j.status,
                "policy_decision": j.policy_decision,
            }
            for j in held
        ],
        "worker_id": "mock-worker-1",
        "worker_health": "ok",
    }


@router.get("/jobs/{job_id}")
def job_detail(
    job_id: str,
    ctx: AuthContext = Depends(_moderator),
    db: Session = Depends(get_db),
):
    job = db.get(GenerationJob, job_id)
    if not job:
        raise AppError("JOB_NOT_FOUND", "Job not found.", 404)
    write_audit(
        db,
        action="admin.job_viewed",
        target_type="generation_job",
        target_id=job.id,
        actor_user_id=ctx.user.id,
        actor_role=ctx.user.role,
    )
    db.commit()
    crypto = get_crypto()
    return {
        "id": job.id,
        "user_id": job.user_id,
        "status": job.status,
        "prompt": crypto.decrypt(job.prompt_encrypted),
        "negative_prompt": crypto.decrypt(job.negative_prompt_encrypted),
        "policy_decision": job.policy_decision,
        "moderation_state": job.moderation_state,
        "parameters": job.parameters,
        "credit_cost": job.credit_cost,
    }


@router.post("/jobs/{job_id}/decision")
def decide(
    job_id: str,
    payload: ModerationDecisionRequest,
    ctx: AuthContext = Depends(_moderator),
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
):
    job = db.get(GenerationJob, job_id)
    if not job:
        raise AppError("JOB_NOT_FOUND", "Job not found.", 404)
    user = db.get(User, job.user_id)
    action = payload.decision.upper()
    if action == "APPROVE":
        job.moderation_state = ModerationState.APPROVED
        if job.status == JobStatus.QUEUED:
            settings = get_settings()
            if settings.job_execution == "inline":
                process_job_by_id(db, settings, get_crypto(), storage, job.id)
    elif action == "BLOCK":
        job.status = JobStatus.BLOCKED
        job.moderation_state = ModerationState.REJECTED
        from app.services.credits import release_credits

        if job.reservation_ledger_event_id:
            release_credits(
                db, job.user_id, job.id, job.credit_cost, "MODERATION_BLOCK"
            )
    elif action == "SUSPEND":
        if user:
            user.status = UserStatus.SUSPENDED
        job.status = JobStatus.BLOCKED
        job.moderation_state = ModerationState.ESCALATED
    elif action == "BAN":
        if user:
            user.status = UserStatus.BANNED
        job.status = JobStatus.BLOCKED
        job.moderation_state = ModerationState.ESCALATED
    else:
        raise AppError("INVALID_DECISION", "Unknown moderation decision.")
    db.add(
        EnforcementAction(
            user_id=job.user_id,
            job_id=job.id,
            actor_user_id=ctx.user.id,
            action=action,
            reason_code=payload.reason_code,
            rationale=payload.rationale,
            preserve_evidence=payload.preserve_evidence,
        )
    )
    write_audit(
        db,
        action="admin.enforcement",
        target_type="generation_job",
        target_id=job.id,
        actor_user_id=ctx.user.id,
        actor_role=ctx.user.role,
        metadata={"decision": action, "reason_code": payload.reason_code},
    )
    db.commit()
    return {"ok": True, "status": job.status, "moderation_state": job.moderation_state}


@router.get("/reports")
def reports(
    ctx: AuthContext = Depends(_moderator),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(Report).order_by(Report.created_at.desc()).limit(100)
    ).all()
    write_audit(
        db,
        action="admin.reports_viewed",
        target_type="system",
        actor_user_id=ctx.user.id,
        actor_role=ctx.user.role,
    )
    db.commit()
    return [
        {"id": r.id, "category": r.category, "status": r.status, "job_id": r.job_id}
        for r in rows
    ]


@router.get("/credits/mismatches")
def mismatches(
    ctx: AuthContext = Depends(
        require_roles(UserRole.FINANCE, UserRole.SUPER_ADMIN, UserRole.SYSTEM_ADMIN)
    ),
    db: Session = Depends(get_db),
):
    write_audit(
        db,
        action="admin.credit_mismatch_viewed",
        target_type="system",
        actor_user_id=ctx.user.id,
        actor_role=ctx.user.role,
    )
    db.commit()
    user_ids = db.scalars(select(CreditLedger.user_id).distinct()).all()
    results = [reconcile_user(db, uid) for uid in user_ids]
    return {"users": results}


@router.post("/credits/adjust")
def adjust(
    payload: LedgerAdjustRequest,
    ctx: AuthContext = Depends(require_roles(UserRole.FINANCE, UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    if not payload.rationale or not payload.reason_code:
        raise AppError(
            "REASON_REQUIRED", "Adjustments require a reason code and rationale."
        )
    event = append_event(
        db,
        user_id=payload.user_id,
        event_type=LedgerEventType.MANUAL_ADJUSTMENT,
        amount=payload.amount,
        idempotency_key=f"adjust:{payload.user_id}:{payload.reason_code}:{utcnow().isoformat()}",
        reason_code=payload.reason_code,
        created_by_user_id=ctx.user.id,
        metadata={"rationale": payload.rationale},
    )
    write_audit(
        db,
        action="admin.credit_adjustment",
        target_type="user",
        target_id=payload.user_id,
        actor_user_id=ctx.user.id,
        actor_role=ctx.user.role,
        metadata={"amount": payload.amount, "reason_code": payload.reason_code},
    )
    db.commit()
    return {"event_id": event.id, "balance": ledger_balance(db, payload.user_id)}


@router.post("/break-glass")
def break_glass(
    payload: BreakGlassRequest,
    ctx: AuthContext = Depends(
        require_roles(UserRole.SYSTEM_ADMIN, UserRole.SUPER_ADMIN)
    ),
    db: Session = Depends(get_db),
):
    access = BreakGlassAccess(
        actor_user_id=ctx.user.id,
        target_user_id=payload.target_user_id,
        reason_code=payload.reason_code,
        rationale=payload.rationale,
        expires_at=utcnow() + timedelta(minutes=payload.ttl_minutes),
    )
    db.add(access)
    write_audit(
        db,
        action="admin.break_glass",
        target_type="user",
        target_id=payload.target_user_id,
        actor_user_id=ctx.user.id,
        actor_role=ctx.user.role,
        metadata={
            "reason_code": payload.reason_code,
            "ttl_minutes": payload.ttl_minutes,
        },
    )
    db.commit()
    return {"id": access.id, "expires_at": access.expires_at}


@router.get("/users/{user_id}")
def user_support(
    user_id: str,
    ctx: AuthContext = Depends(require_roles(UserRole.SUPPORT, UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise AppError("USER_NOT_FOUND", "User not found.", 404)
    write_audit(
        db,
        action="admin.user_viewed",
        target_type="user",
        target_id=user.id,
        actor_user_id=ctx.user.id,
        actor_role=ctx.user.role,
    )
    db.commit()
    return {
        "id": user.id,
        "email": user.email,
        "status": user.status,
        "role": user.role,
        "age_verification_status": user.age_verification_status,
        "outputs_visible": False,
        "note": "Support does not receive image content by default.",
    }
