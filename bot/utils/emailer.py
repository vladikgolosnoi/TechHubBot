from __future__ import annotations

import asyncio
import logging
from email.message import EmailMessage
from typing import Iterable

import aiosmtplib

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def send_email(subject: str, body: str, recipients: Iterable[str]) -> None:
    recipients = list(recipients)
    if not recipients:
        return
    if not settings.has_smtp_credentials:
        logger.info("SMTP credentials are not configured. Skipping email send: %s", subject)
        return

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(body)

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            start_tls=True,
        )
        logger.info("Email sent to %s", recipients)
    except Exception as exc:  # pragma: no cover - this is best effort logging
        logger.exception("Failed to send email: %s", exc)


def send_email_background(subject: str, body: str, recipients: Iterable[str]) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(send_email(subject, body, recipients))
    except RuntimeError:
        asyncio.run(send_email(subject, body, recipients))
