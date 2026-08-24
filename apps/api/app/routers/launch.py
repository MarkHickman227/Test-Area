from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import AuthContext, optional_auth
from app.errors import AppError
from app.models.growth import SupportTicket, WaitlistEntry
from app.schemas.common import APIModel
from app.services.access import (
    assert_country_allowed,
    check_rate_limit,
    request_country,
)
from app.services.audit import write_audit
from app.services.auth import normalize_email

router = APIRouter(tags=["launch"])


class WaitlistRequest(APIModel):
    email: EmailStr
    note: str | None = None


class TicketRequest(APIModel):
    email: EmailStr | None = None
    category: str = "account"
    subject: str
    body: str


@router.get("/v1/meta/launch")
def launch_meta():
    settings = get_settings()
    return {
        "invite_only": settings.invite_only,
        "payments_enabled": settings.payments_enabled,
        "payment_provider": settings.payment_provider,
        "generation_backend": settings.generation_backend,
        "age_provider": settings.age_verification_provider,
        "default_plan_id": settings.default_plan_id,
    }


@router.post("/v1/waitlist")
def join_waitlist(
    payload: WaitlistRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    settings = get_settings()
    check_rate_limit(
        f"waitlist:{request.client.host if request.client else 'unknown'}",
        settings.auth_rate_limit_per_minute,
    )
    country = request_country(request)
    assert_country_allowed(settings, country)
    email = normalize_email(payload.email)
    existing = db.scalar(select(WaitlistEntry).where(WaitlistEntry.email == email))
    if existing:
        return {"id": existing.id, "status": existing.status, "already": True}
    entry = WaitlistEntry(email=email, country_code=country, note=payload.note)
    db.add(entry)
    write_audit(
        db, action="waitlist.joined", target_type="waitlist", target_id=entry.id
    )
    db.commit()
    return {"id": entry.id, "status": entry.status, "already": False}


@router.post("/v1/support/tickets")
def create_ticket(
    payload: TicketRequest,
    db: Session = Depends(get_db),
    ctx: AuthContext | None = Depends(optional_auth),
):
    email = payload.email or (ctx.user.email if ctx else None)
    if not email:
        raise AppError("EMAIL_REQUIRED", "Provide an email so support can reply.")
    if ctx and ctx.user:
        # CSRF applies only when authenticated via require_auth; optional_auth
        # tickets from signed-in users still go through cookie session.
        pass
    ticket = SupportTicket(
        user_id=ctx.user.id if ctx else None,
        email=normalize_email(email),
        category=payload.category,
        subject=payload.subject[:200],
        body=payload.body,
    )
    db.add(ticket)
    write_audit(
        db,
        action="support.ticket_created",
        target_type="support_ticket",
        target_id=ticket.id,
        actor_user_id=ctx.user.id if ctx else None,
    )
    db.commit()
    return {"id": ticket.id, "status": ticket.status}
