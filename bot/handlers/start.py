from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from ..config import get_settings
from ..keyboards.common import admin_menu, main_menu
from ..services.club import ClubService

router = Router()
settings = get_settings()


@router.message(CommandStart())
async def cmd_start(message: Message, club_service: ClubService) -> None:
    user = await club_service.ensure_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )
    is_member = user.status == user.status.ACTIVE
    await message.answer(
        "Добро пожаловать в ИТ-Клуб! Используйте меню ниже, чтобы управлять профилем и участием.",
        reply_markup=main_menu(is_member=is_member),
    )
    if message.from_user.id in settings.admin_ids:
        await message.answer(
            "Вы вошли как администратор. Откройте админ-панель через меню.",
            reply_markup=admin_menu(),
        )
