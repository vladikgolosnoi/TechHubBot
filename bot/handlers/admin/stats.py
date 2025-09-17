from aiogram import F, Router
from aiogram.types import Message

from ...config import get_settings
from ...services.club import ClubService

router = Router()
settings = get_settings()


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


@router.message(F.text == "Статистика")
async def show_stats(message: Message, club_service: ClubService) -> None:
    if not is_admin(message.from_user.id):
        return
    stats = await club_service.get_statistics()
    await message.answer(
        "Статистика клуба:\n"
        f"Пользователей всего: {stats['users_total']}\n"
        f"Активных участников: {stats['members_active']}\n"
        f"Заявок в ожидании: {stats['applications_pending']}\n"
        f"Команд: {stats['teams_total']}\n"
        f"Всего мероприятий: {stats['events_total']}\n"
        f"Ближайших мероприятий: {stats['upcoming_events']}\n"
        f"Регистраций на мероприятия: {stats['event_registrations']}\n"
    )
