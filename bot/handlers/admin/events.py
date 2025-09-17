import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from ...config import get_settings
from ...services.club import ClubService
from ...utils.states import EventCreateState, EventPhotoState
from ...keyboards.common import event_template_keyboard

router = Router()
settings = get_settings()
tz = ZoneInfo(settings.timezone)

EVENT_TEMPLATES = {
    "online": {
        "description": "Онлайн-встреча. Ссылка будет отправлена участникам заранее.",
        "location": "Онлайн",
    },
    "offline": {
        "description": "Очное мероприятие в пространстве ИТ-Клуба.",
        "location": "Офис ИТ-Клуба",
    },
}


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


def parse_datetime(text: str) -> datetime:
    return datetime.strptime(text, "%d.%m.%Y %H:%M").replace(tzinfo=tz).astimezone(timezone.utc)


@router.message(F.text == "Мероприятия (админ)")
async def admin_events(message: Message, club_service: ClubService) -> None:
    if not is_admin(message.from_user.id):
        return
    events = await club_service.list_events()
    if not events:
        await message.answer("Мероприятий пока нет. Используйте 'Создать мероприятие' для добавления.")
        return
    rows = [[InlineKeyboardButton(text=event.title, callback_data=f"admin:event:view:{event.id}")]
            for event in events]
    rows.append([InlineKeyboardButton(text="➕ Создать мероприятие", callback_data="admin:event:create")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer(
        "Список мероприятий. Выберите нужное, чтобы открыть действия:",
        reply_markup=keyboard,
    )


@router.message(F.text == "Создать мероприятие")
async def event_create_start(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.set_state(EventCreateState.template)
    await state.update_data(mode="create")
    await message.answer(
        "Выберите шаблон мероприятия или свободный ввод:",
        reply_markup=event_template_keyboard(),
    )


@router.message(F.text.startswith("Редактировать мероприятие"))
async def event_edit_start(message: Message, state: FSMContext, club_service: ClubService) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 3 or not parts[2].isdigit():
        await message.answer("Укажите ID мероприятия.")
        return
    event = await club_service.get_event(int(parts[2]))
    if not event:
        await message.answer("Мероприятие не найдено.")
        return
    await state.set_state(EventCreateState.title)
    await state.update_data(
        mode="edit",
        event_id=event.id,
        original={
            "title": event.title,
            "description": event.description,
            "location": event.location,
            "registration_start": event.registration_start,
            "registration_end": event.registration_end,
            "start_at": event.start_at,
            "end_at": event.end_at,
            "capacity": event.capacity,
        },
        title=event.title,
        description=event.description,
        location=event.location,
        registration_start=event.registration_start,
        registration_end=event.registration_end,
        start_at=event.start_at,
        end_at=event.end_at,
        capacity=event.capacity,
    )
    await message.answer(f"Введите новое название (или /skip чтобы оставить '{event.title}'):")


@router.message(EventCreateState.title)
async def event_set_title(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if message.text != "/skip" or data.get("mode") == "create":
        await state.update_data(title=message.text.strip())
    await state.set_state(EventCreateState.description)
    current = (await state.get_data()).get("description")
    if current:
        await message.answer(
            f"Опишите мероприятие (или отправьте /skip, чтобы оставить \"{current}\"):"
        )
    else:
        await message.answer("Опишите мероприятие (или отправьте /skip):")


@router.message(EventCreateState.description)
async def event_set_description(message: Message, state: FSMContext) -> None:
    if message.text != "/skip":
        await state.update_data(description=message.text.strip())
    await state.set_state(EventCreateState.location)
    current = (await state.get_data()).get("location")
    if current:
        await message.answer(
            f"Укажите место проведения (или отправьте /skip, чтобы оставить \"{current}\"):"
        )
    else:
        await message.answer("Укажите место проведения (или отправьте /skip):")


@router.message(EventCreateState.location)
async def event_set_location(message: Message, state: FSMContext) -> None:
    if message.text != "/skip":
        await state.update_data(location=message.text.strip())
    await state.set_state(EventCreateState.registration_start)
    await message.answer("Дата начала регистрации (дд.мм.гггг чч:мм):")


@router.message(EventCreateState.registration_start)
async def event_set_reg_start(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if message.text == "/skip" and data.get("mode") == "edit":
        await state.update_data(registration_start=data["original"]["registration_start"])
    else:
        try:
            dt = parse_datetime(message.text)
        except ValueError:
            await message.answer("Некорректный формат. Используйте дд.мм.гггг чч:мм")
            return
        await state.update_data(registration_start=dt)
    await state.set_state(EventCreateState.registration_end)
    await message.answer("Дата окончания регистрации (дд.мм.гггг чч:мм) или /skip:")


@router.message(EventCreateState.registration_end)
async def event_set_reg_end(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if message.text == "/skip" and data.get("mode") == "edit":
        await state.update_data(registration_end=data["original"]["registration_end"])
    else:
        try:
            dt = parse_datetime(message.text)
        except ValueError:
            await message.answer("Некорректный формат. Используйте дд.мм.гггг чч:мм")
            return
        await state.update_data(registration_end=dt)
    await state.set_state(EventCreateState.start_at)
    await message.answer("Дата начала мероприятия (дд.мм.гггг чч:мм) или /skip:")


@router.message(EventCreateState.start_at)
async def event_set_start(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if message.text == "/skip" and data.get("mode") == "edit":
        await state.update_data(start_at=data["original"]["start_at"])
    else:
        try:
            dt = parse_datetime(message.text)
        except ValueError:
            await message.answer("Некорректный формат. Используйте дд.мм.гггг чч:мм")
            return
        await state.update_data(start_at=dt)
    await state.set_state(EventCreateState.end_at)
    await message.answer("Дата окончания мероприятия (дд.мм.гггг чч:мм) или /skip:")


@router.message(EventCreateState.end_at)
async def event_set_end(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if message.text == "/skip" and data.get("mode") == "edit":
        await state.update_data(end_at=data["original"]["end_at"])
    else:
        try:
            dt = parse_datetime(message.text)
        except ValueError:
            await message.answer("Некорректный формат. Используйте дд.мм.гггг чч:мм")
            return
        await state.update_data(end_at=dt)
    await state.set_state(EventCreateState.capacity)
    await message.answer("Введите вместимость (число) или /skip для неограниченной:")


@router.message(EventCreateState.capacity)
async def event_set_capacity(message: Message, state: FSMContext, club_service: ClubService) -> None:
    data = await state.get_data()
    if message.text == "/skip" and data.get("mode") == "edit":
        capacity = data["original"]["capacity"]
    elif message.text != "/skip":
        if not message.text.isdigit():
            await message.answer("Введите число или /skip.")
            return
        capacity = int(message.text)
    else:
        capacity = None
    try:
        if data.get("mode") == "edit":
            event = await club_service.get_event(data["event_id"])
            await club_service.update_event(
                event,
                title=data.get("title"),
                description=data.get("description"),
                location=data.get("location"),
                registration_start=data.get("registration_start"),
                registration_end=data.get("registration_end"),
                start_at=data.get("start_at"),
                end_at=data.get("end_at"),
                capacity=capacity,
                admin_id=message.from_user.id,
            )
            await message.answer("Мероприятие обновлено.")
        else:
            await club_service.create_event(
                title=data.get("title"),
                description=data.get("description"),
                location=data.get("location"),
                registration_start=data.get("registration_start"),
                registration_end=data.get("registration_end"),
                start_at=data.get("start_at"),
                end_at=data.get("end_at"),
                capacity=capacity,
                admin_id=message.from_user.id,
                template=data.get("template"),
            )
            await message.answer("Мероприятие создано.")
    except ValueError as exc:
        await message.answer(f"Не удалось сохранить мероприятие: {exc}")
        return
    await state.clear()


@router.message(F.text.startswith("История мероприятия"))
async def event_history(message: Message, club_service: ClubService) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 3 or not parts[2].isdigit():
        await message.answer("Формат: История мероприятия <id>")
        return
    event_id = int(parts[2])
    logs = await club_service.get_event_logs(event_id)
    if not logs:
        await message.answer("Записей об изменениях не найдено.")
        return
    lines = [f"История мероприятия #{event_id}:"]
    for log in logs:
        timestamp = log.created_at.astimezone(tz).strftime("%d.%m %H:%M") if log.created_at else "-"
        details = ""
        if log.payload:
            try:
                payload = json.loads(log.payload)
                details = " — " + ", ".join(f"{k}: {v}" for k, v in payload.items() if v)
            except json.JSONDecodeError:
                details = f" — {log.payload}"
        lines.append(f"{timestamp}: {log.action.value} (admin {log.admin_id}){details}")
    await message.answer("\n".join(lines))


@router.message(F.text.startswith("Фото мероприятия"))
async def event_photo_request(message: Message, state: FSMContext, club_service: ClubService) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 3 or not parts[2].isdigit():
        await message.answer("Формат: Фото мероприятия <id>")
        return
    event = await club_service.get_event(int(parts[2]))
    if not event:
        await message.answer("Мероприятие не найдено.")
        return
    await state.set_state(EventPhotoState.waiting_photo)
    await state.update_data(event_id=event.id)
    await message.answer("Отправьте фото для мероприятия или /cancel.")


@router.message(EventPhotoState.waiting_photo, F.photo)
async def event_photo_upload(message: Message, state: FSMContext, club_service: ClubService) -> None:
    data = await state.get_data()
    event = await club_service.get_event(data.get("event_id"))
    if not event:
        await message.answer("Мероприятие не найдено.")
        await state.clear()
        return
    file_id = message.photo[-1].file_id
    await club_service.set_event_photo(event, file_id, admin_id=message.from_user.id)
    await message.answer("Фото мероприятия обновлено.")
    await state.clear()


@router.message(EventPhotoState.waiting_photo)
async def event_photo_invalid(message: Message, state: FSMContext) -> None:
    if message.text and message.text.lower() == "/cancel":
        await state.clear()
        await message.answer("Загрузка фото отменена.")
        return
    await message.answer("Нужно отправить фотографию или /cancel.")


@router.message(F.text.startswith("Удалить мероприятие"))
async def event_delete(message: Message, club_service: ClubService) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 3 or not parts[2].isdigit():
        await message.answer("Укажите ID мероприятия.")
        return
    event = await club_service.get_event(int(parts[2]))
    if not event:
        await message.answer("Мероприятие не найдено.")
        return
    await club_service.delete_event(event)
    await message.answer("Мероприятие удалено.")


@router.callback_query(F.data.startswith("admin:event:view:"))
async def admin_event_view(call: CallbackQuery, club_service: ClubService) -> None:
    await call.answer()
    if not is_admin(call.from_user.id):
        return
    event_id = int(call.data.split(":")[-1])
    event = await club_service.get_event(event_id)
    if not event:
        await call.message.answer("Мероприятие не найдено.")
        return
    text = (
        f"#{event.id} {event.title}\n"
        f"Локация: {event.location or 'не указана'}\n"
        f"Регистрация: {event.registration_start:%d.%m %H:%M} — {event.registration_end:%d.%m %H:%M}\n"
        f"Проведение: {event.start_at:%d.%m %H:%M} — {event.end_at:%d.%m %H:%M}\n"
        f"Вместимость: {event.capacity or 'без ограничений'}\n"
        f"Описание: {event.description or '—'}"
    )
    actions = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Редактировать", callback_data=f"admin:event:edit:{event.id}")],
            [InlineKeyboardButton(text="Удалить", callback_data=f"admin:event:delete:{event.id}")],
            [InlineKeyboardButton(text="Фото", callback_data=f"admin:event:photo:{event.id}")],
            [InlineKeyboardButton(text="История", callback_data=f"admin:event:history:{event.id}")],
        ]
    )
    if event.photo_file_id:
        await call.message.answer_photo(event.photo_file_id, caption=text, reply_markup=actions)
    else:
        await call.message.answer(text, reply_markup=actions)


@router.callback_query(F.data.startswith("admin:event:delete:"))
async def admin_event_delete(call: CallbackQuery, club_service: ClubService) -> None:
    await call.answer()
    if not is_admin(call.from_user.id):
        return
    event_id = int(call.data.split(":")[-1])
    event = await club_service.get_event(event_id)
    if not event:
        await call.message.answer("Мероприятие не найдено.")
        return
    await club_service.delete_event(event)
    await call.message.answer("Мероприятие удалено.")


@router.callback_query(F.data.startswith("admin:event:photo:"))
async def admin_event_photo(call: CallbackQuery, state: FSMContext, club_service: ClubService) -> None:
    await call.answer()
    if not is_admin(call.from_user.id):
        return
    event_id = int(call.data.split(":")[-1])
    event = await club_service.get_event(event_id)
    if not event:
        await call.message.answer("Мероприятие не найдено.")
        return
    await state.set_state(EventPhotoState.waiting_photo)
    await state.update_data(event_id=event.id)
    await call.message.answer("Отправьте фото для мероприятия или /cancel.")


@router.callback_query(F.data.startswith("admin:event:history:"))
async def admin_event_history(call: CallbackQuery, club_service: ClubService) -> None:
    await call.answer()
    if not is_admin(call.from_user.id):
        return
    event_id = int(call.data.split(":")[-1])
    logs = await club_service.get_event_logs(event_id)
    if not logs:
        await call.message.answer("Записей об изменениях не найдено.")
        return
    lines = [f"История мероприятия #{event_id}:"]
    for log in logs:
        timestamp = log.created_at.astimezone(tz).strftime("%d.%m %H:%M") if log.created_at else "-"
        details = ""
        if log.payload:
            try:
                payload = json.loads(log.payload)
                details = " — " + ", ".join(f"{k}: {v}" for k, v in payload.items() if v)
            except json.JSONDecodeError:
                details = f" — {log.payload}"
        lines.append(f"{timestamp}: {log.action.value} (admin {log.admin_id}){details}")
    await call.message.answer("\n".join(lines))


@router.callback_query(F.data.startswith("admin:event:edit:"))
async def admin_event_edit_button(call: CallbackQuery, state: FSMContext, club_service: ClubService) -> None:
    await call.answer()
    if not is_admin(call.from_user.id):
        return
    event_id = int(call.data.split(":")[-1])
    event = await club_service.get_event(event_id)
    if not event:
        await call.message.answer("Мероприятие не найдено.")
        return
    await state.set_state(EventCreateState.title)
    await state.update_data(
        mode="edit",
        event_id=event.id,
        original={
            "title": event.title,
            "description": event.description,
            "location": event.location,
            "registration_start": event.registration_start,
            "registration_end": event.registration_end,
            "start_at": event.start_at,
            "end_at": event.end_at,
            "capacity": event.capacity,
        },
        title=event.title,
        description=event.description,
        location=event.location,
        registration_start=event.registration_start,
        registration_end=event.registration_end,
        start_at=event.start_at,
        end_at=event.end_at,
        capacity=event.capacity,
    )
    await call.message.answer(f"Введите новое название (или /skip чтобы оставить '{event.title}'):")
@router.callback_query(F.data.startswith("eventTemplate:"))
async def event_template_selected(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    choice = call.data.split(":", 1)[1]
    template = EVENT_TEMPLATES.get(choice)
    await state.update_data(template=choice)
    if template:
        await state.update_data(
            description=template.get("description"),
            location=template.get("location"),
        )
        await call.message.answer(
            "Шаблон применён. Поля можно изменить на следующих шагах.",
        )
    else:
        await call.message.answer("Включён свободный ввод всех данных.")
    await state.set_state(EventCreateState.title)
    await call.message.answer("Введите название мероприятия:")
    await call.answer()
@router.callback_query(F.data == "admin:event:create")
async def admin_event_create_button(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    if not is_admin(call.from_user.id):
        return
    await state.set_state(EventCreateState.template)
    await state.update_data(mode="create")
    await call.message.answer(
        "Выберите шаблон мероприятия или свободный ввод:",
        reply_markup=event_template_keyboard(),
    )
