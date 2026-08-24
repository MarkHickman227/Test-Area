from __future__ import annotations

import hashlib
import logging
import smtplib
from email.message import EmailMessage

from app.config import Settings

logger = logging.getLogger("privatecanvas.mail")


class MailService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.outbox: list[dict] = []

    def send(self, to_email: str, subject: str, body: str) -> None:
        record = {"to": to_email, "subject": subject, "body": body}
        self.outbox.append(record)
        if self.settings.mail_backend == "console" or self.settings.mail_console:
            logger.info("mail_console to=%s subject=%s", to_email, subject)
            logger.debug("mail_body %s", body)
            return
        msg = EmailMessage()
        msg["From"] = self.settings.smtp_from
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as smtp:
            smtp.send_message(msg)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_optional(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
