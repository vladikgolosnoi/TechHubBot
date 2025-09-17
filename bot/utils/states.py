from aiogram.fsm.state import State, StatesGroup


class RegistrationState(StatesGroup):
    full_name = State()
    email = State()
    phone = State()
    group = State()
    photo = State()
    motivation = State()


class ProfileEditState(StatesGroup):
    full_name = State()
    email = State()
    phone = State()
    profession = State()
    company = State()
    group = State()


class TeamCreateState(StatesGroup):
    name = State()
    description = State()
    is_permanent = State()


class TeamInviteState(StatesGroup):
    team_id = State()
    user_query = State()


class EventCreateState(StatesGroup):
    template = State()
    title = State()
    description = State()
    location = State()
    registration_start = State()
    registration_end = State()
    start_at = State()
    end_at = State()
    capacity = State()


class EventEditState(StatesGroup):
    select_event = State()


class SearchState(StatesGroup):
    query = State()


class ProfilePhotoState(StatesGroup):
    waiting_photo = State()


class TeamPhotoState(StatesGroup):
    waiting_photo = State()


class EventPhotoState(StatesGroup):
    waiting_photo = State()
