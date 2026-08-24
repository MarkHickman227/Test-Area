from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models.base import utcnow
from app.models.billing import CreditLedger
from app.models.enums import LedgerEventType


def ledger_balance(db: Session, user_id: str) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(CreditLedger.amount), 0)).where(
            CreditLedger.user_id == user_id
        )
    )
    return int(total or 0)


def append_event(
    db: Session,
    *,
    user_id: str,
    event_type: LedgerEventType,
    amount: int,
    idempotency_key: str,
    reason_code: str,
    related_job_id: str | None = None,
    related_payment_id: str | None = None,
    created_by_user_id: str | None = None,
    metadata: dict | None = None,
) -> CreditLedger:
    existing = db.scalar(
        select(CreditLedger).where(CreditLedger.idempotency_key == idempotency_key)
    )
    if existing:
        return existing
    event = CreditLedger(
        user_id=user_id,
        event_type=event_type.value,
        amount=amount,
        related_job_id=related_job_id,
        related_payment_id=related_payment_id,
        idempotency_key=idempotency_key,
        reason_code=reason_code,
        extra_metadata=metadata or {},
        created_by_user_id=created_by_user_id,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(event)
    db.flush()
    return event


def reserve_credits(
    db: Session, user_id: str, job_id: str, amount: int
) -> CreditLedger:
    if amount <= 0:
        raise AppError("INVALID_CREDIT_AMOUNT", "Credit cost must be positive.")
    balance = ledger_balance(db, user_id)
    if balance < amount:
        raise AppError("INSUFFICIENT_CREDITS", "Not enough credits for this job.", 402)
    return append_event(
        db,
        user_id=user_id,
        event_type=LedgerEventType.CREDIT_RESERVATION,
        amount=-amount,
        idempotency_key=f"reserve:{job_id}",
        reason_code="JOB_RESERVE",
        related_job_id=job_id,
        metadata={"cost": amount},
    )


def capture_credits(
    db: Session, user_id: str, job_id: str, amount: int
) -> CreditLedger:
    return append_event(
        db,
        user_id=user_id,
        event_type=LedgerEventType.CREDIT_CAPTURE,
        amount=0,
        idempotency_key=f"capture:{job_id}",
        reason_code="JOB_CAPTURE",
        related_job_id=job_id,
        metadata={"cost": amount},
    )


def release_credits(
    db: Session, user_id: str, job_id: str, amount: int, reason: str
) -> CreditLedger:
    return append_event(
        db,
        user_id=user_id,
        event_type=LedgerEventType.CREDIT_RELEASE,
        amount=amount,
        idempotency_key=f"release:{job_id}",
        reason_code=reason,
        related_job_id=job_id,
        metadata={"cost": amount},
    )


def grant_promotional(db: Session, user_id: str, amount: int, key: str) -> CreditLedger:
    return append_event(
        db,
        user_id=user_id,
        event_type=LedgerEventType.PROMOTIONAL_GRANT,
        amount=amount,
        idempotency_key=key,
        reason_code="PROMOTIONAL_GRANT",
    )


def reconcile_user(db: Session, user_id: str) -> dict:
    events = db.scalars(
        select(CreditLedger).where(CreditLedger.user_id == user_id)
    ).all()
    balance = sum(e.amount for e in events)
    reserved = sum(
        -e.amount for e in events if e.event_type == LedgerEventType.CREDIT_RESERVATION
    )
    released = sum(
        e.amount for e in events if e.event_type == LedgerEventType.CREDIT_RELEASE
    )
    captured_jobs = {
        e.related_job_id
        for e in events
        if e.event_type == LedgerEventType.CREDIT_CAPTURE
    }
    open_holds = (
        reserved
        - released
        - sum(
            int((e.extra_metadata or {}).get("cost") or 0)
            for e in events
            if e.event_type == LedgerEventType.CREDIT_CAPTURE
        )
    )
    return {
        "user_id": user_id,
        "balance": balance,
        "event_count": len(events),
        "open_holds": open_holds,
        "captured_jobs": len(captured_jobs),
    }
