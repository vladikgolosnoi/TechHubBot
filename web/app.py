from __future__ import annotations

import json
from typing import Any, AsyncIterator

from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse

from bot.db import init_db, session_scope
from bot.services.club import ClubService
from bot.models import RegistrationStatus

app = FastAPI(title="IT Club Dashboard")


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()


async def get_service() -> AsyncIterator[ClubService]:
    async with session_scope() as session:
        yield ClubService(session)


@app.get("/api/stats")
async def api_stats(service: ClubService = Depends(get_service)) -> dict[str, Any]:
    return await service.get_statistics()


@app.get("/", response_class=HTMLResponse)
async def dashboard(service: ClubService = Depends(get_service)) -> HTMLResponse:
    stats = await service.get_statistics()
    events = await service.list_events()
    event_titles = [event.title for event in events]
    registrations = [
        sum(1 for reg in event.registrations if reg.status == RegistrationStatus.REGISTERED)
        for event in events
    ]
    stats_labels = [
        "Пользователи",
        "Активные",
        "Команды",
        "Мероприятия",
        "Регистрации",
    ]
    stats_values = [
        stats["users_total"],
        stats["members_active"],
        stats["teams_total"],
        stats["events_total"],
        stats["event_registrations"],
    ]
    events_data = json.dumps({
        "labels": event_titles,
        "values": registrations,
    }, ensure_ascii=False)
    stats_data = json.dumps({
        "labels": stats_labels,
        "values": stats_values,
    }, ensure_ascii=False)
    upcoming = [
        {
            "title": event.title,
            "time": event.start_at.strftime("%d.%m %H:%M"),
            "location": event.location or "—",
        }
        for event in events[:5]
    ]
    upcoming_html = "".join(
        f"<li><strong>{item['title']}</strong> — {item['time']} ({item['location']})</li>"
        for item in upcoming
    ) or "<li>Пока нет событий</li>"

    html = f"""
    <!DOCTYPE html>
    <html lang=\"ru\">
    <head>
        <meta charset=\"utf-8\" />
        <title>Панель ИТ-Клуба</title>
        <script src=\"https://cdn.jsdelivr.net/npm/chart.js\"></script>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 2rem; background: #f5f6fa; }}
            h1 {{ margin-bottom: 1rem; }}
            .cards {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 2rem; }}
            .card {{ background: white; border-radius: 12px; padding: 1rem; box-shadow: 0 2px 8px rgba(0,0,0,0.08); flex: 1 1 200px; }}
            canvas {{ max-width: 100%; height: 320px; }}
        </style>
    </head>
    <body>
        <h1>Статистика ИТ-Клуба</h1>
        <div class=\"cards\">
            <div class=\"card\"><canvas id=\"statsChart\"></canvas></div>
            <div class=\"card\"><canvas id=\"eventsChart\"></canvas></div>
        </div>
        <div class=\"card\">
            <h2>Ближайшие мероприятия</h2>
            <ul>{upcoming_html}</ul>
        </div>
        <script>
            const statsData = {stats_data};
            const eventsData = {events_data};
            new Chart(document.getElementById('statsChart'), {{
                type: 'bar',
                data: {{
                    labels: statsData.labels,
                    datasets: [{{
                        label: 'Обзор',
                        data: statsData.values,
                        backgroundColor: '#4e73df'
                    }}]
                }},
                options: {{responsive: true, plugins: {{legend: {{display: false}}}}}}
            }});
            new Chart(document.getElementById('eventsChart'), {{
                type: 'line',
                data: {{
                    labels: eventsData.labels,
                    datasets: [{{
                        label: 'Регистрации',
                        data: eventsData.values,
                        borderColor: '#1cc88a',
                        tension: 0.25,
                        fill: false
                    }}]
                }},
                options: {{responsive: true, plugins: {{legend: {{position: 'bottom'}}}}}}
            }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
