"""Send applications through a connected Unipile email or LinkedIn account."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


def unipile_configured(settings: Any) -> bool:
    return bool(
        getattr(settings, "unipile_dsn", None)
        and getattr(settings, "unipile_api_key", None)
        and (
            getattr(settings, "unipile_email_account_id", None)
            or getattr(settings, "unipile_account_id", None)
        )
    )


def _base_url(settings: Any) -> str:
    dsn = str(getattr(settings, "unipile_dsn", "") or "").rstrip("/")
    parsed = urlparse(dsn)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return dsn


async def send_unipile_email(
    settings: Any,
    *,
    to_email: str,
    subject: str,
    body: str,
) -> bool:
    account_id = getattr(settings, "unipile_email_account_id", None) or getattr(
        settings, "unipile_account_id", None
    )
    url = f"{_base_url(settings)}/api/v1/emails"
    payload = {
        "account_id": account_id,
        "to": [{"identifier": to_email}],
        "subject": subject,
        "body": body,
    }
    return await _post(settings, url, payload, "email")


async def send_unipile_linkedin(
    settings: Any,
    *,
    attendee_id: str,
    text: str,
) -> bool:
    account_id = getattr(settings, "unipile_account_id", None)
    if not account_id or not attendee_id:
        return False
    url = f"{_base_url(settings)}/api/v1/chats"
    payload = {
        "account_id": account_id,
        "attendees_ids": [attendee_id],
        "text": text,
    }
    return await _post(settings, url, payload, "linkedin")


async def _post(settings: Any, url: str, payload: dict[str, Any], channel: str) -> bool:
    headers = {
        "X-API-KEY": settings.unipile_api_key,
        "accept": "application/json",
        "content-type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError:
        logger.exception("Unipile %s send failed", channel)
        return False
    if resp.status_code >= 400:
        logger.error("Unipile %s error %s: %s", channel, resp.status_code, resp.text[:300])
        return False
    return True
