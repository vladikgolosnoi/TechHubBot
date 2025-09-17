from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ...config import get_settings
from ...services.club import ClubService
from ...utils.states import SearchState

router = Router()
settings = get_settings()


@router.message(F.text == "Поиск")
async def search_prompt(message: Message, state: FSMContext) -> None:
    await state.set_state(SearchState.query)
    await message.answer("Введите название команды для поиска:")


@router.message(SearchState.query)
async def search_results(message: Message, state: FSMContext, club_service: ClubService) -> None:
    query = message.text.strip()
    if not query:
        await message.answer("Введите текст для поиска.")
        return
    teams = await club_service.search_teams(query)

    if not teams:
        await message.answer("Команды не найдены. Попробуйте другой запрос.")
        await state.clear()
        return

    team_builder = InlineKeyboardBuilder()
    for team in teams:
        label = f"{team.name} (капитан {team.owner.full_name})"
        team_builder.button(text=label, callback_data=f"team:view:{team.id}")
    team_builder.adjust(1)
    await message.answer("Найденные команды:", reply_markup=team_builder.as_markup())
    await state.clear()
