from typing import Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ...keyboards.common import team_actions
from ...models import MembershipStatus
from ...services.club import ClubService
from ...utils.states import TeamCreateState, TeamInviteState, TeamPhotoState

router = Router()


def teams_menu_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text="Создать команду", callback_data="team:create")
    builder.button(text="Все команды", callback_data="team:list")
    return builder


def team_list_keyboard(teams) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for team in teams:
        builder.button(text=team.name, callback_data=f"team:view:{team.id}")
    if builder.buttons:
        builder.adjust(1)
        return builder.as_markup()
    return InlineKeyboardMarkup(inline_keyboard=[])


def format_team(team, current_user_id: int) -> str:
    members = ", ".join(
        f"{member.user.full_name} (@{member.user.username})" if member.user.username else member.user.full_name
        for member in team.members
    ) or "нет участников"
    owner_mark = " (ваша)" if team.owner_id == current_user_id else ""
    permanence = "постоянная" if team.is_permanent else "временная"
    return (
        f"Команда: {team.name}{owner_mark}\n"
        f"Тип: {permanence}\n"
        f"Капитан: {team.owner.full_name}\n"
        f"Участники: {members}"
    )


async def send_team_card(message: Message, team, current_user_id: int, *, reply_markup) -> None:
    text = format_team(team, current_user_id)
    if team.photo_file_id:
        await message.answer_photo(
            team.photo_file_id,
            caption=text,
            reply_markup=reply_markup,
        )
    else:
        await message.answer(
            text,
            reply_markup=reply_markup,
        )


def team_members_keyboard(team) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for member in team.members:
        builder.button(
            text=member.user.full_name,
            callback_data=f"user:view:{member.user.id}",
        )
    if builder.buttons:
        builder.adjust(1)
        return builder.as_markup()
    return None


@router.message(F.text == "Команды")
async def show_user_teams(message: Message, club_service: ClubService) -> None:
    user = await club_service.ensure_user(
        message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    teams = await club_service.list_user_teams(user.id)
    if not teams:
        await message.answer(
            "У вас пока нет команд. Создайте новую или присоединитесь к существующей.",
            reply_markup=teams_menu_keyboard().as_markup(),
        )
        return
    await message.answer("Ваши команды:", reply_markup=teams_menu_keyboard().as_markup())
    await message.answer(
        "Выберите команду:",
        reply_markup=team_list_keyboard(teams),
    )


@router.callback_query(F.data == "team:list")
async def list_all_teams(call: CallbackQuery, club_service: ClubService) -> None:
    await call.answer()
    teams = await club_service.list_teams()
    if not teams:
        await call.message.answer("Команд пока нет.")
        return
    await call.message.answer(
        "Все команды, выберите нужную:",
        reply_markup=team_list_keyboard(teams),
    )


@router.callback_query(F.data == "team:create")
async def team_create_start(call: CallbackQuery, state: FSMContext, club_service: ClubService) -> None:
    await call.answer()
    user = await club_service.get_user(call.from_user.id)
    if not user:
        await call.message.answer("Сначала подайте заявку в клуб.")
        return
    if user.status != MembershipStatus.ACTIVE:
        await call.message.answer("Создавать команды могут только утверждённые участники.")
        return
    await state.set_state(TeamCreateState.name)
    await call.message.answer("Введите название команды:")


@router.message(TeamCreateState.name)
async def team_create_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(TeamCreateState.description)
    await message.answer("Опишите команду (или отправьте /skip):")


@router.message(TeamCreateState.description)
async def team_create_description(message: Message, state: FSMContext) -> None:
    if message.text != "/skip":
        await state.update_data(description=message.text.strip())
    await state.set_state(TeamCreateState.is_permanent)
    await message.answer("Команда постоянная? Ответьте да/нет:")


@router.message(TeamCreateState.is_permanent)
async def team_create_finish(
    message: Message,
    state: FSMContext,
    club_service: ClubService,
) -> None:
    answer = message.text.lower()
    is_permanent = answer.startswith("д")
    data = await state.get_data()
    user = await club_service.get_user(message.from_user.id)
    try:
        team = await club_service.create_team(
            owner=user,
            name=data["name"],
            description=data.get("description"),
            is_permanent=is_permanent,
        )
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await state.clear()
    await message.answer(
        f"Команда {team.name} создана!",
        reply_markup=team_actions(team.id, True),
    )


@router.callback_query(F.data.startswith("team:view:"))
async def team_view(call: CallbackQuery, club_service: ClubService) -> None:
    await call.answer()
    team_id = int(call.data.split(":")[2])
    team = await club_service.get_team(team_id)
    if not team:
        await call.message.answer("Команда не найдена.")
        return
    viewer = await club_service.get_user(call.from_user.id)
    await send_team_card(
        call.message,
        team,
        call.from_user.id,
        reply_markup=team_actions(team.id, bool(viewer and team.owner_id == viewer.id)),
    )
    members_keyboard = team_members_keyboard(team)
    if members_keyboard:
        await call.message.answer(
            "Откройте профиль участника:",
            reply_markup=members_keyboard,
        )


@router.callback_query(F.data.startswith("team:join:"))
async def team_join(call: CallbackQuery, club_service: ClubService) -> None:
    await call.answer()
    team_id = int(call.data.split(":")[2])
    team = await club_service.get_team(team_id)
    if not team:
        await call.message.answer("Команда не найдена.")
        return
    user = await club_service.get_user(call.from_user.id)
    if not user or user.status != MembershipStatus.ACTIVE:
        await call.message.answer("Присоединяться могут только участники клуба.")
        return
    if team.owner_id == user.id:
        await call.message.answer("Вы уже капитан этой команды.")
        return
    try:
        await club_service.add_member_to_team(team, user)
        await call.message.answer("Вы добавлены в команду.")
    except ValueError as exc:
        await call.message.answer(str(exc))


@router.callback_query(F.data.startswith("team:photo:view:"))
async def team_photo_view(call: CallbackQuery, club_service: ClubService) -> None:
    await call.answer()
    team_id = int(call.data.split(":")[-1])
    team = await club_service.get_team(team_id)
    if not team:
        await call.message.answer("Команда не найдена.")
        return
    if team.photo_file_id:
        await call.message.answer_photo(team.photo_file_id, caption=team.name)
    else:
        await call.message.answer("Фото команды пока не добавлено.")


@router.callback_query(F.data.startswith("team:photo:update:"))
async def team_photo_update(call: CallbackQuery, state: FSMContext, club_service: ClubService) -> None:
    await call.answer()
    team_id = int(call.data.split(":")[-1])
    team = await club_service.get_team(team_id)
    if not team:
        await call.message.answer("Команда не найдена.")
        return
    owner = await club_service.get_user(call.from_user.id)
    if not owner or owner.id != team.owner_id:
        await call.message.answer("Только капитан может обновлять фото команды.")
        return
    await state.set_state(TeamPhotoState.waiting_photo)
    await state.update_data(team_id=team_id)
    await call.message.answer("Отправьте новое фото команды или /cancel.")


@router.message(TeamPhotoState.waiting_photo, F.photo)
async def team_photo_upload(message: Message, state: FSMContext, club_service: ClubService) -> None:
    data = await state.get_data()
    team = await club_service.get_team(data.get("team_id"))
    if not team:
        await message.answer("Команда не найдена.")
        await state.clear()
        return
    requester = await club_service.get_user(message.from_user.id)
    if not requester or requester.id != team.owner_id:
        await message.answer("Только капитан может обновлять фото.")
        await state.clear()
        return
    file_id = message.photo[-1].file_id
    await club_service.set_team_photo(team, file_id)
    await message.answer("Фото команды обновлено.")
    await state.clear()


@router.message(TeamPhotoState.waiting_photo)
async def team_photo_invalid(message: Message, state: FSMContext) -> None:
    if message.text and message.text.lower() == "/cancel":
        await state.clear()
        await message.answer("Загрузка фото отменена.")
        return
    await message.answer("Пожалуйста, отправьте фотографию или /cancel.")


@router.callback_query(F.data.startswith("team:add:"))
async def team_add_member(call: CallbackQuery, state: FSMContext, club_service: ClubService) -> None:
    await call.answer()
    team_id = int(call.data.split(":")[2])
    team = await club_service.get_team(team_id)
    if not team:
        await call.message.answer("Команда не найдена.")
        return
    owner = await club_service.get_user(call.from_user.id)
    if not owner or owner.id != team.owner_id:
        await call.message.answer("Добавлять участников может только капитан.")
        return
    await state.update_data(team_id=team_id, action="add")
    await state.set_state(TeamInviteState.user_query)
    await call.message.answer("Введите username (@user) или ID участника:")


async def _resolve_user(query: str, club_service: ClubService) -> Optional[int]:
    query = query.strip()
    if query.startswith("@"):
        user = await club_service.get_user_by_username(query)
        return user.id if user else None
    if query.isdigit():
        user = await club_service.get_user(int(query))
        if user:
            return user.id
        user = await club_service.get_user_by_id(int(query))
        return user.id if user else None
    users = await club_service.search_users(query)
    if len(users) == 1:
        return users[0].id
    return None


@router.callback_query(F.data.startswith("team:remove:"))
async def team_remove_member(call: CallbackQuery, state: FSMContext, club_service: ClubService) -> None:
    await call.answer()
    team_id = int(call.data.split(":")[2])
    team = await club_service.get_team(team_id)
    if not team:
        await call.message.answer("Команда не найдена.")
        return
    owner = await club_service.get_user(call.from_user.id)
    if not owner or owner.id != team.owner_id:
        await call.message.answer("Удалять участников может только капитан.")
        return
    await state.update_data(team_id=team_id, action="remove")
    await state.set_state(TeamInviteState.user_query)
    await call.message.answer("Введите username или ID участника, которого нужно удалить:")


@router.message(TeamInviteState.user_query)
async def team_member_action_finish(message: Message, state: FSMContext, club_service: ClubService) -> None:
    data = await state.get_data()
    team = await club_service.get_team(data["team_id"])
    if not team:
        await message.answer("Команда не найдена.")
        await state.clear()
        return
    user_id = await _resolve_user(message.text, club_service)
    if not user_id:
        await message.answer("Не удалось найти участника по запросу.")
        return
    user = await club_service.get_user_by_id(user_id)
    if not user:
        await message.answer("Участник не найден в базе. Убедитесь, что он уже подал заявку.")
        return
    action = data.get("action")
    if action == "remove":
        if user.id == team.owner_id:
            await message.answer("Нельзя удалить капитана. Передайте капитана другому участнику и попробуйте снова.")
            return
        await club_service.remove_member_from_team(team, user)
        await message.answer(f"Участник {user.full_name} удалён из команды {team.name}.")
    else:
        if user.status != MembershipStatus.ACTIVE:
            await message.answer("Добавить можно только участника клуба со статусом ACTIVE.")
            return
        try:
            await club_service.add_member_to_team(team, user)
            await message.answer(f"{user.full_name} добавлен в команду {team.name}.")
        except ValueError as exc:
            await message.answer(str(exc))
    await state.clear()


@router.callback_query(F.data.startswith("team:delete:"))
async def team_delete(call: CallbackQuery, club_service: ClubService) -> None:
    await call.answer()
    team_id = int(call.data.split(":")[2])
    team = await club_service.get_team(team_id)
    if not team:
        await call.message.answer("Команда не найдена.")
        return
    owner = await club_service.get_user(call.from_user.id)
    if not owner or owner.id != team.owner_id:
        await call.message.answer("Удалять команду может только капитан.")
        return
    await club_service.delete_team(team)
    await call.message.answer("Команда удалена.")
