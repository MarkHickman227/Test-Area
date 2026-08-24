from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import AuthContext, require_roles
from app.errors import AppError
from app.models.billing import CreditLedger, Plan
from app.models.enums import JobStatus, UserRole
from app.models.generation import GenerationJob
from app.models.growth import InviteCode, SupportTicket, WaitlistEntry
from app.models.user import User
from app.schemas.common import APIModel
from app.services.audit import write_audit
from app.services.credits import ledger_balance, reconcile_user

router = APIRouter(prefix="/v1/admin", tags=["ops"])


class InviteCreate(APIModel):
    code: str
    max_uses: int = 1
    note: str | None = None


class TicketPatch(APIModel):
    status: str
    internal_note: str | None = None


@router.get("/capacity")
def capacity(
    ctx: AuthContext = Depends(
        require_roles(UserRole.SYSTEM_ADMIN, UserRole.MODERATOR, UserRole.SUPER_ADMIN)
    ),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    queued = int(
        db.scalar(
            select(func.count())
            .select_from(GenerationJob)
            .where(GenerationJob.status == JobStatus.QUEUED)
        )
        or 0
    )
    running = int(
        db.scalar(
            select(func.count())
            .select_from(GenerationJob)
            .where(GenerationJob.status == JobStatus.RUNNING)
        )
        or 0
    )
    write_audit(
        db,
        action="admin.capacity_viewed",
        target_type="system",
        actor_user_id=ctx.user.id,
        actor_role=ctx.user.role,
    )
    db.commit()
    return {
        "queue_depth": queued,
        "queue_max_depth": settings.queue_max_depth,
        "running": running,
        "worker_slots": settings.worker_slots,
        "headroom": max(0, settings.queue_max_depth - queued),
        "job_timeout_seconds": settings.job_timeout_seconds,
    }


@router.get("/finance/summary")
def finance_summary(
    ctx: AuthContext = Depends(
        require_roles(UserRole.FINANCE, UserRole.SUPER_ADMIN, UserRole.SYSTEM_ADMIN)
    ),
    db: Session = Depends(get_db),
):
    write_audit(
        db,
        action="admin.finance_summary",
        target_type="system",
        actor_user_id=ctx.user.id,
        actor_role=ctx.user.role,
    )
    db.commit()
    users = db.scalars(select(CreditLedger.user_id).distinct()).all()
    reconciled = [reconcile_user(db, uid) for uid in users]
    open_holds = sum(int(row.get("open_holds") or 0) for row in reconciled)
    return {
        "payments_enabled": get_settings().payments_enabled,
        "user_count": len(users),
        "open_holds": open_holds,
        "users": reconciled[:100],
    }


@router.get("/support/users")
def support_users(
    q: str = Query(min_length=3, max_length=120),
    ctx: AuthContext = Depends(require_roles(UserRole.SUPPORT, UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    needle = q.strip().lower()
    rows = db.scalars(
        select(User).where(User.email.like(f"%{needle}%")).limit(20)
    ).all()
    write_audit(
        db,
        action="admin.support_search",
        target_type="user",
        actor_user_id=ctx.user.id,
        actor_role=ctx.user.role,
        metadata={"q_len": len(needle)},
    )
    db.commit()
    return [
        {
            "id": u.id,
            "email": u.email,
            "status": u.status,
            "plan_id": u.plan_id,
            "age_verification_status": u.age_verification_status,
            "balance": ledger_balance(db, u.id),
            "outputs_visible": False,
        }
        for u in rows
    ]


@router.get("/support/tickets")
def list_tickets(
    ctx: AuthContext = Depends(require_roles(UserRole.SUPPORT, UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(SupportTicket).order_by(SupportTicket.created_at.desc()).limit(100)
    ).all()
    return [
        {
            "id": t.id,
            "email": t.email,
            "subject": t.subject,
            "status": t.status,
            "category": t.category,
        }
        for t in rows
    ]


@router.patch("/support/tickets/{ticket_id}")
def patch_ticket(
    ticket_id: str,
    payload: TicketPatch,
    ctx: AuthContext = Depends(require_roles(UserRole.SUPPORT, UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise AppError("TICKET_NOT_FOUND", "Ticket not found.", 404)
    ticket.status = payload.status
    if payload.internal_note:
        ticket.internal_note = payload.internal_note
        ticket.assignee_user_id = ctx.user.id
    write_audit(
        db,
        action="admin.ticket_updated",
        target_type="support_ticket",
        target_id=ticket.id,
        actor_user_id=ctx.user.id,
        actor_role=ctx.user.role,
    )
    db.commit()
    return {"ok": True, "status": ticket.status}


@router.get("/waitlist")
def waitlist(
    ctx: AuthContext = Depends(require_roles(UserRole.SUPPORT, UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(WaitlistEntry).order_by(WaitlistEntry.created_at.desc()).limit(200)
    ).all()
    return [
        {
            "id": r.id,
            "email": r.email,
            "status": r.status,
            "country_code": r.country_code,
        }
        for r in rows
    ]


@router.post("/invites")
def create_invite(
    payload: InviteCreate,
    ctx: AuthContext = Depends(
        require_roles(UserRole.SYSTEM_ADMIN, UserRole.SUPER_ADMIN)
    ),
    db: Session = Depends(get_db),
):
    code = payload.code.strip().upper()
    if db.scalar(select(InviteCode).where(InviteCode.code == code)):
        raise AppError("INVITE_EXISTS", "That invite code already exists.", 409)
    invite = InviteCode(code=code, max_uses=payload.max_uses, note=payload.note)
    db.add(invite)
    write_audit(
        db,
        action="admin.invite_created",
        target_type="invite",
        target_id=invite.id,
        actor_user_id=ctx.user.id,
        actor_role=ctx.user.role,
    )
    db.commit()
    return {"id": invite.id, "code": invite.code, "max_uses": invite.max_uses}


@router.get("/plans")
def list_plans(
    ctx: AuthContext = Depends(
        require_roles(UserRole.FINANCE, UserRole.SUPER_ADMIN, UserRole.SYSTEM_ADMIN)
    ),
    db: Session = Depends(get_db),
):
    rows = db.scalars(select(Plan)).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "max_images_per_job": p.max_images_per_job,
            "allows_priority": p.allows_priority,
            "hourly_job_limit": p.hourly_job_limit,
        }
        for p in rows
    ]
