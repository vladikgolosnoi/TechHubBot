from . import events, gamification, profile, registration, search, teams

user_routers = [
    registration.router,
    profile.router,
    teams.router,
    events.router,
    gamification.router,
    search.router,
]

__all__ = ["user_routers"]
