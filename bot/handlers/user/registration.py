from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram import Bot

from ...config import get_settings
from ...keyboards.common import application_actions, main_menu
from ...services.club import ClubService
from ...utils.emailer import send_email_background
from ...utils.states import RegistrationState

router = Router()
settings = get_settings()


@router.message(F.text == "Подать заявку")
async def start_registration(message: Message, state: FSMContext, club_service: ClubService) -> None:
    user = await club_service.ensure_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )
    if user.status == user.status.ACTIVE:
        await message.answer("Вы уже участник клуба.")
        return
    await state.set_state(RegistrationState.full_name)
    await message.answer("Введите ваше ФИО:")


@router.message(RegistrationState.full_name)
async def registration_name(message: Message, state: FSMContext) -> None:
    await state.update_data(full_name=message.text.strip())
    await state.set_state(RegistrationState.email)
    await message.answer("Укажите ваш email для связи:")


@router.message(RegistrationState.email)
async def registration_email(message: Message, state: FSMContext) -> None:
    if "@" not in message.text:
        await message.answer("Похоже, email указан неверно. Попробуйте ещё раз.")
        return
    await state.update_data(email=message.text.strip())
    await state.set_state(RegistrationState.phone)
    await message.answer("Оставьте телефон (или напишите '-' если не хотите указывать):")


@router.message(RegistrationState.phone)
async def registration_phone(message: Message, state: FSMContext) -> None:
    phone = message.text.strip()
    if phone == "-":
        phone = None
    await state.update_data(phone=phone)
    await state.set_state(RegistrationState.group)
    await message.answer("Укажите вашу учебную группу или команду (например, ДЗ-11):")


@router.message(RegistrationState.group)
async def registration_group(message: Message, state: FSMContext) -> None:
    await state.update_data(group=message.text.strip())
    await state.set_state(RegistrationState.photo)
    await message.answer("Прикрепите ваше фото (или отправьте /skip, чтобы пропустить):")


@router.message(RegistrationState.photo, F.photo)
async def registration_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(photo=message.photo[-1].file_id)
    await state.set_state(RegistrationState.motivation)
    await message.answer("Расскажите о себе и зачем хотите вступить в клуб:")


@router.message(RegistrationState.photo)
async def registration_photo_skip(message: Message, state: FSMContext) -> None:
    if message.text and message.text.lower() == "/skip":
        await state.update_data(photo=None)
        await state.set_state(RegistrationState.motivation)
        await message.answer("Расскажите о себе и зачем хотите вступить в клуб:")
        return
    await message.answer("Пожалуйста, отправьте фотографию или /skip, чтобы пропустить этот шаг.")


@router.message(RegistrationState.motivation)
async def registration_finish(
    message: Message,
    state: FSMContext,
    club_service: ClubService,
    bot: Bot,
) -> None:
    data = await state.get_data()
    user = await club_service.ensure_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=data.get("full_name") or message.from_user.full_name,
    )
    application = await club_service.submit_application(
        user=user,
        motivation=message.text.strip(),
        email=data["email"],
        phone=data.get("phone"),
        group_name=data.get("group"),
        photo_file_id=data.get("photo"),
    )
    await state.clear()
    await message.answer(
        "Спасибо! Заявка отправлена на рассмотрение. Мы уведомим вас после решения.",
        reply_markup=main_menu(is_member=False),
    )

    subject = "Новая заявка в ИТ-Клуб"
    body = (
        f"Поступила новая заявка от {user.full_name} (@{user.username or 'нет username'}).\n"
        f"Email: {user.email}\n"
        f"Телефон: {user.phone or 'не указан'}\n"
        f"Группа: {user.group_name or 'не указана'}\n"
        f"Мотивация: {application.motivation or 'не указана'}\n"
    )
    if settings.has_smtp_credentials:
        send_email_background(subject, body, [settings.smtp_from])

    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(
                admin_id,
                body,
                reply_markup=application_actions(application.id),
            )
        except Exception:
            # Ignore delivery issues to keep user flow smooth
            continue


@router.message(F.text == "Выйти из клуба")
async def leave_club(message: Message, club_service: ClubService) -> None:
    user = await club_service.get_user(message.from_user.id)
    if not user:
        await message.answer("Вы ещё не зарегистрированы.")
        return
    await club_service.reset_user(user)
    await message.answer(
        "Вы успешно вышли из клуба. Возвратитесь в любое время, если захотите вновь подать заявку.",
        reply_markup=main_menu(is_member=False),
    )
