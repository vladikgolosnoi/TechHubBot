from __future__ import annotations

import asyncio
import logging
from zoneinfo import ZoneInfo

from aiogram import Bot

from ..config import get_settings
from ..db import session_scope
from ..models import RegistrationStatus
from ..utils.emailer import send_email_background
from .club import ClubService

logger = logging.getLogger(__name__)
settings = get_settings()
TZ = ZoneInfo(settings.timezone)


async def reminder_loop(bot: Bot, interval_seconds: int = 1800) -> None:
    while True:
        try:
            async with session_scope() as session:
                club = ClubService(session)
                events = await club.upcoming_events_for_reminder()
                for event in events:
                    start_local = event.start_at.astimezone(TZ).strftime("%d.%m %H:%M")
                    text = (
                        f"Напоминание: {event.title} начнётся {start_local}.\n"
                        f"Локация: {event.location or 'уточните у организаторов'}"
                    )
                    emails = []
                    for registration in event.registrations:
                        if registration.status != RegistrationStatus.REGISTERED:
                            continue
                        try:
                            await bot.send_message(registration.user.telegram_id, text)
                        except Exception as exc:  # pragma: no cover - logging only
                            logger.debug(
                                "Не удалось отправить напоминание tg_id=%s: %s",
                                registration.user.telegram_id,
                                exc,
                            )
                        if registration.user.email:
                            emails.append(registration.user.email)
                    if emails:
                        send_email_background(
                            f"Напоминание о мероприятии: {event.title}",
                            (
                                f"Мероприятие '{event.title}' начнётся {start_local}.\n"
                                f"Место: {event.location or 'уточните у организаторов'}.\n"
                                "До встречи!"
                            ),
                            emails,
                        )
                    await club.mark_event_reminded(event)
        except Exception as exc:  # pragma: no cover - background job
            logger.exception("Ошибка в задаче напоминаний: %s", exc)
        await asyncio.sleep(interval_seconds)


def start_reminder_worker(bot: Bot, interval_seconds: int = 1800) -> asyncio.Task:
    return asyncio.create_task(reminder_loop(bot, interval_seconds))
