from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ...config import get_settings
from ...services.club import ClubService

router = Router()
settings = get_settings()


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


PER_PAGE = 8


def build_users_keyboard(users, page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = []
    for user in users:
        label = f"{user.full_name} (@{user.username})" if user.username else user.full_name
        rows.append([InlineKeyboardButton(text=label, callback_data=f"admin:user:view:{user.id}")])
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅", callback_data=f"admin:users:page:{page - 1}"))
    if page + 1 < total_pages:
        nav_row.append(InlineKeyboardButton(text="➡", callback_data=f"admin:users:page:{page + 1}"))
    if nav_row:
        rows.append(nav_row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text == "Список участников")
async def admin_users(message: Message, club_service: ClubService) -> None:
    if not is_admin(message.from_user.id):
        return
    total = await club_service.count_users()
    if total == 0:
        await message.answer("Пользователи пока не зарегистрированы.")
        return
    total_pages = (total + PER_PAGE - 1) // PER_PAGE
    users = await club_service.list_users_paginated(0, PER_PAGE)
    keyboard = build_users_keyboard(users, page=0, total_pages=total_pages)
    stats = await club_service.get_statistics()
    await message.answer(
        "Участники клуба:\n"
        f"Всего пользователей: {stats['users_total']}\n"
        f"Активные участники: {stats['members_active']}\n"
        "Выберите участника, чтобы открыть профиль.\n"
        "Для поиска используйте, например, 'Проверить Иванов' или 'Проверить @username'.",
        reply_markup=keyboard,
    )


@router.message(F.text.startswith("Проверить "))
async def check_user(message: Message, club_service: ClubService) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(" ", 1)
    if len(parts) < 2:
        await message.answer("Формат: Проверить <запрос> (например, 'Проверить Иванов').")
        return
    query = parts[1].strip()
    if not query:
        await message.answer("Укажите имя, username или ID.")
        return
    users = await club_service.search_users(query, limit=10)
    if not users:
        await message.answer("Ничего не найдено.")
        return
    parts = []
    for user in users:
        parts.append(
            f"ID {user.id}, TG {user.telegram_id}, {user.full_name} (@{user.username or 'нет'})\n"
            f"Email: {user.email or 'нет'}, телефон: {user.phone or 'нет'}, статус: {user.status.value}"
        )
    await message.answer("\n\n".join(parts))


@router.callback_query(F.data.startswith("admin:users:page:"))
async def admin_users_page(call: CallbackQuery, club_service: ClubService) -> None:
    await call.answer()
    if not is_admin(call.from_user.id):
        return
    page = int(call.data.split(":")[-1])
    total = await club_service.count_users()
    total_pages = (total + PER_PAGE - 1) // PER_PAGE
    page = max(0, min(page, max(total_pages - 1, 0)))
    users = await club_service.list_users_paginated(page, PER_PAGE)
    keyboard = build_users_keyboard(users, page, total_pages)
    await call.message.edit_reply_markup(reply_markup=keyboard)


@router.callback_query(F.data.startswith("admin:user:view:"))
async def admin_user_view(call: CallbackQuery, club_service: ClubService) -> None:
    await call.answer()
    if not is_admin(call.from_user.id):
        return
    user_id = int(call.data.split(":")[-1])
    user = await club_service.get_user_by_id(user_id)
    if not user:
        await call.message.answer("Участник не найден.")
        return

    lines = [
        f"Имя: {user.full_name}",
        f"Username: @{user.username}" if user.username else "Username: отсутствует",
        f"Email: {user.email or 'не указан'}",
        f"Телефон: {user.phone or 'не указан'}",
        f"Группа: {user.group_name or 'не указана'}",
        f"Статус: {user.status.value}",
        f"Баллы: {user.points}",
    ]
    caption = "\n".join(lines)

    markup = None
    if user.username:
        markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Написать", url=f"https://t.me/{user.username}")]]
        )

    if user.photo_file_id:
        await call.message.answer_photo(user.photo_file_id, caption=caption, reply_markup=markup)
    else:
        await call.message.answer(caption, reply_markup=markup)
