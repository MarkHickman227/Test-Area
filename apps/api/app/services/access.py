from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError
from app.models.base import ensure_aware, utcnow
from app.models.growth import InviteCode
from app.services.mail import hash_optional

_hits: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def reset_rate_limits() -> None:
    with _lock:
        _hits.clear()


def request_country(request: Request) -> str | None:
    for header in ("cf-ipcountry", "x-country-code", "x-geo-country"):
        value = request.headers.get(header)
        if value:
            return value.strip().upper()[:8]
    return None


def assert_country_allowed(settings: Settings, country: str | None) -> None:
    blocked = {
        item.strip().upper()
        for item in (settings.blocked_countries or "").split(",")
        if item.strip()
    }
    if country and country in blocked:
        raise AppError(
            "REGION_BLOCKED",
            "This service is not available in your region.",
            403,
        )


def check_rate_limit(key: str, limit: int, window_seconds: int = 60) -> None:
    if limit <= 0:
        return
    now = time.time()
    with _lock:
        bucket = [ts for ts in _hits[key] if now - ts < window_seconds]
        if len(bucket) >= limit:
            _hits[key] = bucket
            raise AppError(
                "RATE_LIMITED", "Too many requests. Slow down and try again.", 429
            )
        bucket.append(now)
        _hits[key] = bucket


def consume_invite(
    db: Session, code: str | None, settings: Settings
) -> InviteCode | None:
    if not settings.invite_only:
        if not code:
            return None
    if settings.invite_only and not code:
        raise AppError("INVITE_REQUIRED", "Registration is invite-only right now.")
    record = db.scalar(
        select(InviteCode).where(InviteCode.code == code.strip().upper())
    )
    if not record or not record.active:
        raise AppError("INVITE_INVALID", "That invite code is not valid.")
    expires = ensure_aware(record.expires_at)
    if expires and expires < utcnow():
        raise AppError("INVITE_INVALID", "That invite code has expired.")
    if record.use_count >= record.max_uses:
        raise AppError("INVITE_EXHAUSTED", "That invite code has already been used.")
    record.use_count += 1
    return record


def hashed_ip(ip: str | None) -> str | None:
    return hash_optional(ip)
