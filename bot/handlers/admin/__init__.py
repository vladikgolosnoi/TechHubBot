from . import applications, events, exports, stats, teams, users

admin_routers = [
    applications.router,
    users.router,
    teams.router,
    events.router,
    exports.router,
    stats.router,
]

__all__ = ["admin_routers"]
