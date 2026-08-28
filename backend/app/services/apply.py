"""Build and send applications from the full uploaded CV."""

from __future__ import annotations

import logging
import re
import smtplib
from email.message import EmailMessage
from typing import Any

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_BLOCKED_EMAIL = {"example.com", "sentry.io", "wixpress.com"}


def build_application_pack(job: dict[str, Any], cv_profile: dict[str, Any] | None) -> dict[str, str]:
    profile = cv_profile or {}
    summary = (profile.get("summary") or "").strip()
    roles = ", ".join(str(r) for r in (profile.get("roles") or [])[:6])
    title = job.get("title") or "this role"
    company = job.get("company") or "your team"
    letter = (
        f"Dear Hiring Manager,\n\n"
        f"I am applying for {title} at {company}. "
        f"This application is based on my uploaded CV"
        f"{f' ({roles})' if roles else ''}.\n\n"
        f"{summary[:1800] or 'Please see my CV for enterprise and solutions architecture experience.'}\n\n"
        f"Kind regards\n"
    )
    return {
        "cover_letter": letter.strip(),
        "cv_summary": (summary or roles)[:1200],
    }


def listing_contact_email(job: dict[str, Any]) -> str | None:
    blob = " ".join(
        [
            str(job.get("description") or ""),
            str(job.get("company") or ""),
            str(job.get("source_url") or ""),
        ]
    )
    for match in _EMAIL_RE.findall(blob):
        domain = match.rsplit("@", 1)[-1].lower()
        if domain in _BLOCKED_EMAIL:
            continue
        return match
    return None


def smtp_configured(settings: Any) -> bool:
    return bool(
        getattr(settings, "smtp_host", None)
        and getattr(settings, "apply_from_email", None)
        and getattr(settings, "smtp_user", None)
        and getattr(settings, "smtp_password", None)
    )


def send_application_email(
    settings: Any,
    job: dict[str, Any],
    pack: dict[str, str],
    cv_text: str,
    to_email: str,
) -> bool:
    message = EmailMessage()
    sender = settings.apply_from_email
    message["From"] = sender
    message["To"] = to_email
    message["Subject"] = f"Application: {job.get('title') or 'Role'} — Mark Hickman"
    body = pack.get("cover_letter") or ""
    if cv_text:
        body += "\n\n--- Uploaded CV ---\n" + cv_text[:15000]
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, int(getattr(settings, "smtp_port", 587) or 587), timeout=20) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
        return True
    except (OSError, smtplib.SMTPException):
        logger.exception("SMTP send failed for %s", job.get("title"))
        return False


async def auto_apply(
    job: dict[str, Any],
    pack: dict[str, str],
    cv_profile: dict[str, Any] | None,
    settings: Any,
) -> dict[str, Any]:
    """Record the application. Email it when SMTP and a listing contact exist."""
    cv_text = ((cv_profile or {}).get("raw_text") or (cv_profile or {}).get("summary") or "").strip()
    contact = listing_contact_email(job)
    emailed = False
    if contact and smtp_configured(settings):
        emailed = send_application_email(settings, job, pack, cv_text, contact)
    return {
        "submitted": True,
        "emailed": emailed,
        "contact_email": contact,
        "source_url": job.get("source_url"),
        "channel": "email" if emailed else "application_pack",
    }
