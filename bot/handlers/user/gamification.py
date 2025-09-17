from aiogram import F, Router
from aiogram.types import Message

from ...services.club import ClubService

router = Router()


@router.message(F.text == "Мои баллы")
async def show_points(message: Message, club_service: ClubService) -> None:
    user = await club_service.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала подайте заявку в клуб.")
        return
    achievements = [
        f"• {ach.achievement.title}" for ach in user.achievements
    ] or ["пока нет достижений"]

    text = (
        f"Баллы: {user.points}\n"
        "Достижения:\n" + "\n".join(achievements) +
        "\n\nБаллы начисляются за участие в мероприятиях."\
        "\nПороги достижений: 50, 150 и 300 баллов."
    )
    await message.answer(text)
