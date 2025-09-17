from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from ...config import get_settings
from ...keyboards.common import event_actions
from ...models import MembershipStatus, RegistrationStatus
from ...services.club import ClubService
from ...utils.emailer import send_email_background

router = Router()
settings = get_settings()
_tz = ZoneInfo(settings.timezone)


def format_event(event) -> str:
    start = event.start_at.astimezone(_tz).strftime("%d.%m %H:%M")
    end = event.end_at.astimezone(_tz).strftime("%d.%m %H:%M")
    reg_start = event.registration_start.astimezone(_tz).strftime("%d.%m %H:%M")
    reg_end = event.registration_end.astimezone(_tz).strftime("%d.%m %H:%M")
    return (
        f"{event.title}\n"
        f"Описание: {event.description or 'нет'}\n"
        f"Локация: {event.location or 'не указана'}\n"
        f"Регистрация: {reg_start} — {reg_end}\n"
        f"Время проведения: {start} — {end}"
    )


async def send_event_card(message: Message, event, registered: bool) -> None:
    caption = format_event(event)
    markup = event_actions(event.id, registered)
    if event.photo_file_id:
        await message.answer_photo(event.photo_file_id, caption=caption, reply_markup=markup)
    else:
        await message.answer(caption, reply_markup=markup)


@router.message(F.text == "Мероприятия")
async def list_events(message: Message, club_service: ClubService) -> None:
    events = await club_service.list_events(only_open=False)
    if not events:
        await message.answer("Пока нет мероприятий.")
        return
    user = await club_service.ensure_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )
    for event in events:
        registered = any(
            r.user_id == user.id and r.status == RegistrationStatus.REGISTERED
            for r in event.registrations
        )
        await send_event_card(message, event, registered)


@router.callback_query(F.data.startswith("event:info:"))
async def event_info(call: CallbackQuery, club_service: ClubService) -> None:
    await call.answer()
    event_id = int(call.data.split(":")[2])
    event = await club_service.get_event(event_id)
    if not event:
        await call.message.answer("Мероприятие не найдено.")
        return
    if event.photo_file_id:
        await call.message.answer_photo(event.photo_file_id, caption=format_event(event))
    else:
        await call.message.answer(format_event(event))


@router.callback_query(F.data.startswith("event:photo:view:"))
async def event_photo_view(call: CallbackQuery, club_service: ClubService) -> None:
    await call.answer()
    event_id = int(call.data.split(":")[3])
    event = await club_service.get_event(event_id)
    if not event:
        await call.message.answer("Мероприятие не найдено.")
        return
    if event.photo_file_id:
        await call.message.answer_photo(event.photo_file_id, caption=event.title)
    else:
        await call.message.answer("Для мероприятия пока нет фото.")


@router.callback_query(F.data.startswith("event:join:"))
async def event_join(call: CallbackQuery, club_service: ClubService) -> None:
    await call.answer()
    event_id = int(call.data.split(":")[2])
    event = await club_service.get_event(event_id)
    if not event:
        await call.message.answer("Мероприятие не найдено.")
        return
    user = await club_service.get_user(call.from_user.id)
    if not user or user.status != MembershipStatus.ACTIVE:
        await call.message.answer("Записываться могут только участники клуба.")
        return
    try:
        await club_service.register_for_event(event, user)
        await call.message.answer("Вы зарегистрированы на мероприятие! Мы начислили вам баллы.")
        if user.email:
            start_local = event.start_at.astimezone(_tz).strftime("%d.%m %H:%M")
            send_email_background(
                f"Регистрация на мероприятие: {event.title}",
                (
                    f"Вы зарегистрированы на '{event.title}'.\n"
                    f"Начало: {start_local}.\n"
                    "До встречи!"
                ),
                [user.email],
            )
    except ValueError as exc:
        await call.message.answer(str(exc))


@router.callback_query(F.data.startswith("event:cancel:"))
async def event_cancel(call: CallbackQuery, club_service: ClubService) -> None:
    await call.answer()
    event_id = int(call.data.split(":")[2])
    event = await club_service.get_event(event_id)
    if not event:
        await call.message.answer("Мероприятие не найдено.")
        return
    user = await club_service.get_user(call.from_user.id)
    if not user:
        await call.message.answer("Сначала подайте заявку в клуб.")
        return
    try:
        await club_service.cancel_registration(event, user)
        await call.message.answer("Регистрация отменена.")
        if user.email:
            send_email_background(
                f"Отмена участия: {event.title}",
                (
                    f"Вы отменили участие в '{event.title}'.\n"
                    "Если передумаете, вы всегда можете зарегистрироваться снова!"
                ),
                [user.email],
            )
    except ValueError as exc:
        await call.message.answer(str(exc))
