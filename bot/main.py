import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from .config import get_settings
from .db import init_db, session_scope
from .handlers.admin import admin_routers
from .handlers.start import router as start_router
from .handlers.user import user_routers
from .middlewares.db import DatabaseMiddleware
from .services.club import ensure_default_achievements
from .services.reminders import start_reminder_worker


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()

    bot = Bot(token=settings.bot_token, parse_mode=ParseMode.HTML)
    dp = Dispatcher()

    db_middleware = DatabaseMiddleware()
    dp.message.middleware(db_middleware)
    dp.callback_query.middleware(db_middleware)

    dp.include_router(start_router)
    for router in user_routers:
        dp.include_router(router)
    for router in admin_routers:
        dp.include_router(router)

    await init_db()
    async with session_scope() as session:
        await ensure_default_achievements(session)

    reminder_task = start_reminder_worker(bot)

    try:
        await dp.start_polling(bot)
    finally:
        reminder_task.cancel()
        with suppress(asyncio.CancelledError):
            await reminder_task


if __name__ == "__main__":
    asyncio.run(main())
