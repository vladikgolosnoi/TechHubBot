from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram import Bot

from ...config import get_settings
from ...keyboards.common import application_actions
from ...models import ApplicationStatus
from ...services.club import ClubService
from ...utils.emailer import send_email_background

router = Router()
settings = get_settings()
tz = ZoneInfo(settings.timezone)


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


@router.message(F.text == "Заявки")
async def list_applications(message: Message, club_service: ClubService) -> None:
    if not is_admin(message.from_user.id):
        return
    applications = await club_service.list_pending_applications()
    if not applications:
        await message.answer("Заявок на рассмотрении нет.")
        return
    for app in applications:
        await message.answer(
            f"#{app.id} — {app.user.full_name}\nEmail: {app.user.email}\nМотивация: {app.motivation or 'не указана'}\n"
            f"История: команда 'История заявки {app.id}'",
            reply_markup=application_actions(app.id),
        )


async def _notify_user(bot: Bot, user_id: int, text: str) -> None:
    try:
        await bot.send_message(user_id, text)
    except Exception:
        pass


@router.callback_query(F.data.startswith("app:approve:"))
async def approve_application(
    call: CallbackQuery,
    club_service: ClubService,
    bot: Bot,
) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Только администратор может это сделать.", show_alert=True)
        return
    app_id = int(call.data.split(":")[2])
    application = await club_service.get_application_by_id(app_id)
    if not application:
        await call.message.answer("Заявка не найдена.")
        return
    if application.status != ApplicationStatus.PENDING:
        await call.message.answer("Заявка уже обработана.")
        return
    await club_service.approve_application(application, admin_id=call.from_user.id)
    await call.message.answer(f"Заявка #{app_id} одобрена.")
    await _notify_user(
        bot,
        application.user.telegram_id,
        "Ваша заявка в ИТ-Клуб одобрена! Добро пожаловать!",
    )
    if application.user.email:
        body = (
            "Здравствуйте!\n\n"
            "Ваша заявка на вступление в ИТ-Клуб принята. "
            "Ждём вас на мероприятиях!"
        )
        send_email_background("Принятие заявки", body, [application.user.email])


@router.callback_query(F.data.startswith("app:reject:"))
async def reject_application(
    call: CallbackQuery,
    club_service: ClubService,
    bot: Bot,
) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Только администратор может это сделать.", show_alert=True)
        return
    app_id = int(call.data.split(":")[2])
    application = await club_service.get_application_by_id(app_id)
    if not application:
        await call.message.answer("Заявка не найдена.")
        return
    if application.status != ApplicationStatus.PENDING:
        await call.message.answer("Заявка уже обработана.")
        return
    await club_service.reject_application(application, admin_id=call.from_user.id)
    await call.message.answer(f"Заявка #{app_id} отклонена.")
    await _notify_user(
        bot,
        application.user.telegram_id,
        "К сожалению, ваша заявка в ИТ-Клуб отклонена. Вы можете подать повторно позднее.",
    )
    if application.user.email:
        body = (
            "Здравствуйте!\n\n"
            "Заявка на вступление в ИТ-Клуб отклонена. "
            "Вы всегда можете подать её снова."
        )
        send_email_background("Заявка отклонена", body, [application.user.email])


@router.message(F.text.startswith("История заявки"))
async def application_history(message: Message, club_service: ClubService) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 3 or not parts[2].isdigit():
        await message.answer("Формат: История заявки <id>")
        return
    app_id = int(parts[2])
    logs = await club_service.get_application_logs(app_id)
    if not logs:
        await message.answer("История решений по заявке отсутствует.")
        return
    lines = [f"История заявки #{app_id}:"]
    for log in logs:
        timestamp = log.created_at.astimezone(tz).strftime("%d.%m %H:%M") if log.created_at else "-"
        comment = f" — {log.comment}" if log.comment else ""
        lines.append(
            f"{timestamp}: {log.decision.value} (admin {log.admin_id}){comment}"
        )
    await message.answer("\n".join(lines))
