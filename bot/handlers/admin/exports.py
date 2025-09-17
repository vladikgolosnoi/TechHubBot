from pathlib import Path

from aiogram import F, Router
from aiogram.types import FSInputFile, Message
from aiogram import Bot

from ...config import get_settings
from ...services.club import ClubService

router = Router()
settings = get_settings()
EXPORT_DIR = Path("exports")


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


@router.message(F.text == "Экспорт данных")
async def export_data(message: Message, club_service: ClubService, bot: Bot) -> None:
    if not is_admin(message.from_user.id):
        return
    EXPORT_DIR.mkdir(exist_ok=True)
    users_csv = await club_service.export_users_csv(EXPORT_DIR / "users.csv")
    teams_csv = await club_service.export_teams_csv(EXPORT_DIR / "teams.csv")
    users_xlsx = await club_service.export_users_xlsx(EXPORT_DIR / "users.xlsx")
    teams_xlsx = await club_service.export_teams_xlsx(EXPORT_DIR / "teams.xlsx")
    await message.answer("Подготовлены файлы, отправляю...")
    for path in [users_csv, teams_csv, users_xlsx, teams_xlsx]:
        await bot.send_document(message.from_user.id, FSInputFile(path))
