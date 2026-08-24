from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.moderation import AuditEvent


def write_audit(
    db: Session,
    *,
    action: str,
    target_type: str,
    target_id: str | None = None,
    actor_user_id: str | None = None,
    actor_role: str | None = None,
    request_id: str | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        created_at=utcnow(),
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        request_id=request_id,
        extra_metadata=metadata or {},
    )
    db.add(event)
    db.flush()
    return event
