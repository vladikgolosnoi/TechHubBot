from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ...keyboards.common import main_menu
from ...models import ApplicationStatus
from ...services.club import ClubService
from ...utils.states import ProfileEditState, ProfilePhotoState

router = Router()


def profile_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text="Редактировать", callback_data="profile:edit")
    builder.button(text="Мои мероприятия", callback_data="profile:events")
    builder.button(text="Мои заявки", callback_data="profile:applications")
    builder.button(text="Обновить фото", callback_data="profile:photo")
    return builder


@router.message(F.text == "Мой профиль")
async def view_profile(message: Message, club_service: ClubService) -> None:
    user = await club_service.ensure_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )
    text = (
        f"Имя: {user.full_name}\n"
        f"Email: {user.email or 'не указан'}\n"
        f"Телефон: {user.phone or 'не указан'}\n"
        f"Профессия: {user.profession or 'не указано'}\n"
        f"Компания: {user.company or 'не указано'}\n"
        f"Группа: {user.group_name or 'не указана'}\n"
        f"Статус: {user.status.value}\n"
        f"Баллы: {user.points}\n"
    )
    if user.photo_file_id:
        await message.answer_photo(
            user.photo_file_id,
            caption=text,
            reply_markup=profile_keyboard().as_markup(),
        )
    else:
        await message.answer(
            text,
            reply_markup=profile_keyboard().as_markup(),
        )


@router.callback_query(F.data == "profile:edit")
async def start_edit(call: CallbackQuery, state: FSMContext, club_service: ClubService) -> None:
    await call.answer()
    user = await club_service.get_user(call.from_user.id)
    if not user:
        await call.message.answer("Сначала подайте заявку.")
        return
    await state.set_state(ProfileEditState.full_name)
    await call.message.answer("Введите новое имя (или оставьте текущее, отправив /skip):")


@router.message(ProfileEditState.full_name)
async def edit_full_name(message: Message, state: FSMContext) -> None:
    if message.text != "/skip":
        await state.update_data(full_name=message.text.strip())
    await state.set_state(ProfileEditState.email)
    await message.answer("Укажите новый email (или /skip):")


@router.message(ProfileEditState.email)
async def edit_email(message: Message, state: FSMContext) -> None:
    if message.text != "/skip":
        if "@" not in message.text:
            await message.answer("Похоже, email неверный. Попробуйте ещё раз или отправьте /skip.")
            return
        await state.update_data(email=message.text.strip())
    await state.set_state(ProfileEditState.phone)
    await message.answer("Обновите телефон (или /skip):")


@router.message(ProfileEditState.phone)
async def edit_phone(message: Message, state: FSMContext) -> None:
    if message.text != "/skip":
        await state.update_data(phone=message.text.strip())
    await state.set_state(ProfileEditState.profession)
    await message.answer("Укажите профессию (или /skip):")


@router.message(ProfileEditState.profession)
async def edit_profession(message: Message, state: FSMContext) -> None:
    if message.text != "/skip":
        await state.update_data(profession=message.text.strip())
    await state.set_state(ProfileEditState.company)
    await message.answer("Укажите компанию (или /skip):")


@router.message(ProfileEditState.company)
async def edit_company(message: Message, state: FSMContext, club_service: ClubService) -> None:
    if message.text != "/skip":
        await state.update_data(company=message.text.strip())
    await state.set_state(ProfileEditState.group)
    await message.answer("Укажите учебную группу (или /skip):")


@router.message(ProfileEditState.group)
async def edit_group(message: Message, state: FSMContext, club_service: ClubService) -> None:
    if message.text != "/skip":
        await state.update_data(group=message.text.strip())
    data = await state.get_data()
    user = await club_service.get_user(message.from_user.id)
    await club_service.update_user_profile(
        user,
        full_name=data.get("full_name"),
        email=data.get("email"),
        phone=data.get("phone"),
        profession=data.get("profession"),
        company=data.get("company"),
        group_name=data.get("group"),
    )
    await state.clear()
    await message.answer(
        "Профиль обновлён.",
        reply_markup=main_menu(is_member=user.status == user.status.ACTIVE),
    )


@router.callback_query(F.data == "profile:events")
async def profile_events(call: CallbackQuery, club_service: ClubService) -> None:
    await call.answer()
    registrations = await club_service.list_user_registrations(call.from_user.id)
    if not registrations:
        await call.message.answer("Вы пока не записаны ни на одно мероприятие.")
        return
    lines = ["Ваши регистрации:"]
    for reg in registrations:
        status = "✅" if reg.status == reg.status.REGISTERED else "❌"
        lines.append(f"{status} {reg.event.title} — {reg.event.start_at:%d.%m %H:%M}")
    await call.message.answer("\n".join(lines))


@router.callback_query(F.data == "profile:applications")
async def profile_applications(call: CallbackQuery, club_service: ClubService) -> None:
    await call.answer()
    user = await club_service.get_user(call.from_user.id)
    if not user or not user.application:
        await call.message.answer("Заявок не найдено.")
        return
    app = user.application
    status_map = {
        ApplicationStatus.PENDING: "На рассмотрении",
        ApplicationStatus.APPROVED: "Принята",
        ApplicationStatus.REJECTED: "Отклонена",
    }
    text = f"Статус заявки: {status_map.get(app.status, app.status.value)}"
    if app.comment:
        text += f"\nКомментарий: {app.comment}"
    await call.message.answer(text)


@router.callback_query(F.data == "profile:photo")
async def profile_photo_prompt(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(ProfilePhotoState.waiting_photo)
    await call.message.answer("Отправьте новое фото профиля или /cancel.")


@router.message(ProfilePhotoState.waiting_photo, F.photo)
async def profile_photo_upload(message: Message, state: FSMContext, club_service: ClubService) -> None:
    user = await club_service.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала подайте заявку в клуб.")
        await state.clear()
        return
    file_id = message.photo[-1].file_id
    await club_service.set_user_photo(user, file_id)
    await message.answer("Фото профиля обновлено.")
    await state.clear()


@router.message(ProfilePhotoState.waiting_photo)
async def profile_photo_invalid(message: Message, state: FSMContext) -> None:
    if message.text and message.text.lower() == "/cancel":
        await state.clear()
        await message.answer("Загрузка фото отменена.")
        return
    await message.answer("Пожалуйста, отправьте фотографию или /cancel.")


@router.callback_query(F.data.startswith("user:view:"))
async def view_other_user(call: CallbackQuery, club_service: ClubService) -> None:
    await call.answer()
    try:
        target_id = int(call.data.split(":")[-1])
    except ValueError:
        await call.message.answer("Неверный идентификатор участника.")
        return
    target = await club_service.get_user_by_id(target_id)
    if not target:
        await call.message.answer("Участник не найден.")
        return

    text_lines = [
        f"Имя: {target.full_name}",
        f"Username: @{target.username}" if target.username else "Username: отсутствует",
        f"Email: {target.email or 'не указан'}",
        f"Телефон: {target.phone or 'не указан'}",
        f"Группа: {target.group_name or 'не указана'}",
        f"Статус: {target.status.value}",
        f"Профессия: {target.profession or 'не указано'}",
        f"Компания: {target.company or 'не указано'}",
        f"Баллы: {target.points}",
    ]
    caption = "\n".join(text_lines)

    markup = None
    if target.username:
        builder = InlineKeyboardBuilder()
        builder.button(text="Написать в Telegram", url=f"https://t.me/{target.username}")
        markup = builder.as_markup()

    if target.photo_file_id:
        await call.message.answer_photo(target.photo_file_id, caption=caption, reply_markup=markup)
    else:
        await call.message.answer(caption, reply_markup=markup)
