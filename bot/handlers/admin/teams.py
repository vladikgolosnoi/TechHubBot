from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from ...config import get_settings
from ...services.club import ClubService

router = Router()
settings = get_settings()


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


@router.message(F.text == "Команды (админ)")
async def admin_teams(message: Message, club_service: ClubService) -> None:
    if not is_admin(message.from_user.id):
        return
    teams = await club_service.list_teams()
    if not teams:
        await message.answer("Команд нет.")
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=team.name, callback_data=f"admin:team:view:{team.id}")]
            for team in teams
        ]
    )
    await message.answer(
        "Команды клуба. Выберите команду, чтобы просмотреть детали:",
        reply_markup=keyboard,
    )


@router.message(F.text.startswith("Удалить команду"))
async def admin_delete_team(message: Message, club_service: ClubService) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 3 or not parts[2].isdigit():
        await message.answer("Укажите ID команды.")
        return
    team = await club_service.get_team(int(parts[2]))
    if not team:
        await message.answer("Команда не найдена.")
        return
    await club_service.delete_team(team)
    await message.answer("Команда удалена.")


@router.message(F.text.startswith("Исключить "))
async def admin_remove_member(message: Message, club_service: ClubService) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await message.answer("Формат: Исключить <team_id> <user_id>")
        return
    team = await club_service.get_team(int(parts[1]))
    if not team:
        await message.answer("Команда не найдена.")
        return
    user = await club_service.get_user_by_id(int(parts[2]))
    if not user:
        await message.answer("Участник не найден.")
        return
    await club_service.remove_member_from_team(team, user)
    await message.answer("Участник удалён из команды.")


@router.callback_query(F.data.startswith("admin:team:view:"))
async def admin_team_view(call: CallbackQuery, club_service: ClubService) -> None:
    await call.answer()
    if not is_admin(call.from_user.id):
        return
    team_id = int(call.data.split(":")[-1])
    team = await club_service.get_team(team_id)
    if not team:
        await call.message.answer("Команда не найдена.")
        return
    members = "\n".join(
        f"• {member.user.full_name} (@{member.user.username})"
        if member.user.username
        else f"• {member.user.full_name}"
        for member in team.members
    ) or "(пока пусто)"
    text = (
        f"#{team.id} {team.name}\n"
        f"Капитан: {team.owner.full_name}\n"
        f"Тип: {'Постоянная' if team.is_permanent else 'Временная'}\n"
        f"Участники:\n{members}\n\n"
        "Команды чата:\n"
        "• Удалить команду ID\n"
        "• Исключить ID_команды ID_участника"
    )
    actions = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Удалить команду", callback_data=f"admin:team:delete:{team.id}")]
        ]
    )
    await call.message.answer(text, reply_markup=actions)


@router.callback_query(F.data.startswith("admin:team:delete:"))
async def admin_team_delete(call: CallbackQuery, club_service: ClubService) -> None:
    await call.answer()
    if not is_admin(call.from_user.id):
        return
    team_id = int(call.data.split(":")[-1])
    team = await club_service.get_team(team_id)
    if not team:
        await call.message.answer("Команда не найдена.")
        return
    await club_service.delete_team(team)
    await call.message.answer("Команда удалена.")
