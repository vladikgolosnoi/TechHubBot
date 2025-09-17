from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def main_menu(is_member: bool) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    if not is_member:
        builder.button(text="Подать заявку")
    builder.button(text="Мой профиль")
    builder.button(text="Команды")
    builder.button(text="Мероприятия")
    builder.button(text="Мои баллы")
    builder.button(text="Поиск")
    builder.button(text="Выйти из клуба")
    builder.adjust(2, 2, 2)
    return builder.as_markup(resize_keyboard=True, input_field_placeholder="Выберите действие")


def admin_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="Заявки")
    builder.button(text="Список участников")
    builder.button(text="Команды (админ)")
    builder.button(text="Мероприятия (админ)")
    builder.button(text="Экспорт данных")
    builder.button(text="Статистика")
    builder.adjust(2, 2, 2)
    return builder.as_markup(resize_keyboard=True, input_field_placeholder="Панель администратора")


def application_actions(app_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Принять", callback_data=f"app:approve:{app_id}")
    builder.button(text="Отклонить", callback_data=f"app:reject:{app_id}")
    builder.adjust(2)
    return builder.as_markup()


def team_actions(team_id: int, is_owner: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Состав", callback_data=f"team:view:{team_id}")
    builder.button(text="Запросить вступление", callback_data=f"team:join:{team_id}")
    builder.button(text="Фото", callback_data=f"team:photo:view:{team_id}")
    if is_owner:
        builder.button(text="Добавить участника", callback_data=f"team:add:{team_id}")
        builder.button(text="Удалить участника", callback_data=f"team:remove:{team_id}")
        builder.button(text="Удалить команду", callback_data=f"team:delete:{team_id}")
        builder.button(text="Обновить фото", callback_data=f"team:photo:update:{team_id}")
    builder.adjust(2)
    return builder.as_markup()


def event_actions(event_id: int, registered: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if registered:
        builder.button(text="Отменить участие", callback_data=f"event:cancel:{event_id}")
    else:
        builder.button(text="Записаться", callback_data=f"event:join:{event_id}")
    builder.button(text="Подробнее", callback_data=f"event:info:{event_id}")
    builder.button(text="Фото", callback_data=f"event:photo:view:{event_id}")
    builder.adjust(2)
    return builder.as_markup()


def pagination_keyboard(prefix: str, page: int, has_more: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if page > 0:
        builder.button(text="⬅", callback_data=f"{prefix}:{page - 1}")
    if has_more:
        builder.button(text="➡", callback_data=f"{prefix}:{page + 1}")
    return builder.as_markup()


def event_template_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Онлайн", callback_data="eventTemplate:online")
    builder.button(text="Оффлайн", callback_data="eventTemplate:offline")
    builder.button(text="Свободный ввод", callback_data="eventTemplate:custom")
    builder.adjust(2)
    return builder.as_markup()
