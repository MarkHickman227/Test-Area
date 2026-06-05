import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.post import AgentSession, LinkedInAccount


def create_session(db: Session, account: LinkedInAccount) -> str:
    raw_token = secrets.token_urlsafe(32)
    session = AgentSession(
        token_hash=hash_session_token(raw_token),
        account_id=account.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours),
    )
    db.add(session)
    db.commit()
    return raw_token


def set_session_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        raw_token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(settings.session_cookie_name)


def hash_session_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def get_current_account(
    db: Session = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> LinkedInAccount:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    session = (
        db.query(AgentSession)
        .filter(AgentSession.token_hash == hash_session_token(session_token))
        .first()
    )
    now = datetime.now(timezone.utc)
    if not session or ensure_aware(session.expires_at) < now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    return session.account


def revoke_session(db: Session, session_token: str | None) -> None:
    if not session_token:
        return
    session = (
        db.query(AgentSession)
        .filter(AgentSession.token_hash == hash_session_token(session_token))
        .first()
    )
    if session:
        db.delete(session)
        db.commit()


def ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
