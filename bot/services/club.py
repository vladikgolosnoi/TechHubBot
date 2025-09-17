from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Sequence

import openpyxl
from openpyxl.workbook import Workbook
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import get_settings
from ..models import (
    Achievement,
    Application,
    ApplicationDecisionLog,
    ApplicationDecisionType,
    ApplicationStatus,
    Event,
    EventChangeAction,
    EventChangeLog,
    EventRegistration,
    MembershipStatus,
    RegistrationStatus,
    Team,
    TeamMember,
    User,
    UserAchievement,
)


settings = get_settings()


class ClubService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # User utilities
    async def get_user(self, telegram_id: int) -> Optional[User]:
        result = await self.session.execute(
            select(User)
            .where(User.telegram_id == telegram_id)
            .options(
                selectinload(User.achievements).selectinload(UserAchievement.achievement),
                selectinload(User.teams).selectinload(TeamMember.team),
                selectinload(User.application),
            )
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        result = await self.session.execute(
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.achievements).selectinload(UserAchievement.achievement),
                selectinload(User.teams).selectinload(TeamMember.team),
                selectinload(User.application),
            )
        )
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> Optional[User]:
        username = username.replace("@", "").lower()
        result = await self.session.execute(
            select(User)
            .where(func.lower(User.username) == username)
            .options(
                selectinload(User.achievements).selectinload(UserAchievement.achievement),
                selectinload(User.teams).selectinload(TeamMember.team),
                selectinload(User.application),
            )
        )
        return result.scalar_one_or_none()

    async def ensure_user(
        self,
        telegram_id: int,
        username: Optional[str],
        full_name: Optional[str] = None,
    ) -> User:
        user = await self.get_user(telegram_id)
        if user:
            # Update username / name in case they changed
            updated = False
            if username and user.username != username:
                user.username = username
                updated = True
            if full_name and user.full_name != full_name:
                user.full_name = full_name
                updated = True
            if updated:
                await self.session.flush()
            return user

        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name or "Без имени",
            email="",
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_user_profile(
        self,
        user: User,
        *,
        full_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        profession: Optional[str] = None,
        company: Optional[str] = None,
        group_name: Optional[str] = None,
    ) -> User:
        if full_name is not None:
            user.full_name = full_name
        if email is not None:
            user.email = email
        if phone is not None:
            user.phone = phone
        if profession is not None:
            user.profession = profession
        if company is not None:
            user.company = company
        if group_name is not None:
            user.group_name = group_name
        await self.session.flush()
        return user

    async def set_user_photo(self, user: User, file_id: str) -> None:
        user.photo_file_id = file_id
        await self.session.flush()

    async def search_users(self, query: str, limit: int = 5) -> Sequence[User]:
        stmt = (
            select(User)
            .order_by(User.full_name.asc())
            .limit(limit)
            .options(
                selectinload(User.achievements).selectinload(UserAchievement.achievement),
                selectinload(User.teams).selectinload(TeamMember.team),
                selectinload(User.application),
            )
        )
        if query.isdigit():
            value = int(query)
            stmt = stmt.where(
                or_(User.telegram_id == value, User.id == value)
            )
        else:
            cleaned = query.lower().replace("@", "")
            stmt = stmt.where(
                or_(
                    func.lower(User.full_name).like(f"%{cleaned}%"),
                    func.lower(User.username).like(f"%{cleaned}%"),
                )
            )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_users_paginated(self, page: int, per_page: int) -> Sequence[User]:
        stmt = (
            select(User)
            .order_by(User.full_name.asc())
            .offset(page * per_page)
            .limit(per_page)
            .options(
                selectinload(User.achievements),
                selectinload(User.teams),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_users(self) -> int:
        return await self.session.scalar(select(func.count(User.id))) or 0

    async def reset_user(self, user: User) -> None:
        await self.session.delete(user)
        await self.session.flush()

    # Application flow
    async def submit_application(
        self,
        user: User,
        motivation: Optional[str],
        email: str,
        phone: Optional[str],
        group_name: Optional[str],
        photo_file_id: Optional[str],
    ) -> Application:
        await self.update_user_profile(
            user,
            email=email,
            phone=phone,
            group_name=group_name,
        )
        if photo_file_id:
            await self.set_user_photo(user, photo_file_id)
        if user.application:
            application = user.application
            if application.status != ApplicationStatus.PENDING:
                application.status = ApplicationStatus.PENDING
                application.decision_at = None
            application.motivation = motivation
        else:
            application = Application(user=user, motivation=motivation)
            self.session.add(application)
        user.status = MembershipStatus.NEW
        await self.session.flush()
        return application

    async def list_pending_applications(self) -> Sequence[Application]:
        result = await self.session.execute(
            select(Application)
            .where(Application.status == ApplicationStatus.PENDING)
            .order_by(Application.created_at.asc())
            .options(selectinload(Application.user))
        )
        return result.scalars().all()

    async def list_applications(self, status: Optional[ApplicationStatus] = None) -> Sequence[Application]:
        stmt = select(Application).order_by(Application.created_at.desc()).options(
            selectinload(Application.user)
        )
        if status:
            stmt = stmt.where(Application.status == status)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def approve_application(
        self, application: Application, comment: Optional[str] = None, admin_id: Optional[int] = None
    ) -> None:
        application.status = ApplicationStatus.APPROVED
        application.comment = comment
        application.decision_at = datetime.utcnow()
        application.user.status = MembershipStatus.ACTIVE
        application.user.email_confirmed = True
        await self.session.flush()
        await self._log_application_decision(
            application,
            ApplicationDecisionType.APPROVED,
            admin_id=admin_id,
            comment=comment,
        )

    async def reject_application(
        self,
        application: Application,
        comment: Optional[str] = None,
        admin_id: Optional[int] = None,
    ) -> None:
        application.status = ApplicationStatus.REJECTED
        application.comment = comment
        application.decision_at = datetime.utcnow()
        application.user.status = MembershipStatus.REJECTED
        await self.session.flush()
        await self._log_application_decision(
            application,
            ApplicationDecisionType.REJECTED,
            admin_id=admin_id,
            comment=comment,
        )

    async def get_application_by_id(self, application_id: int) -> Optional[Application]:
        result = await self.session.execute(
            select(Application)
            .where(Application.id == application_id)
            .options(selectinload(Application.user))
        )
        return result.scalar_one_or_none()

    # Team management
    async def create_team(
        self,
        *,
        owner: User,
        name: str,
        description: Optional[str],
        is_permanent: bool,
    ) -> Team:
        name_lower = name.strip().lower()
        existing = await self.session.scalar(
            select(Team).where(func.lower(Team.name) == name_lower)
        )
        if existing:
            raise ValueError("Команда с таким названием уже существует")
        team = Team(
            owner=owner,
            name=name.strip(),
            description=description,
            is_permanent=is_permanent,
        )
        self.session.add(team)
        await self.session.flush()
        # Add owner as member with role captain
        member = TeamMember(team=team, user=owner, role="captain")
        self.session.add(member)
        await self.session.flush()
        return team

    async def get_team(self, team_id: int) -> Optional[Team]:
        result = await self.session.execute(
            select(Team)
            .where(Team.id == team_id)
            .options(
                selectinload(Team.members).selectinload(TeamMember.user),
                selectinload(Team.owner),
            )
        )
        return result.scalar_one_or_none()

    async def list_teams(self) -> Sequence[Team]:
        result = await self.session.execute(
            select(Team)
            .order_by(Team.name.asc())
            .options(
                selectinload(Team.members).selectinload(TeamMember.user),
                selectinload(Team.owner),
            )
        )
        return result.scalars().all()

    async def list_user_teams(self, user_id: int) -> Sequence[Team]:
        result = await self.session.execute(
            select(Team)
            .join(TeamMember)
            .where(TeamMember.user_id == user_id)
            .order_by(Team.name.asc())
            .options(
                selectinload(Team.members).selectinload(TeamMember.user),
                selectinload(Team.owner),
            )
        )
        return result.scalars().all()

    async def search_teams(self, query: str) -> Sequence[Team]:
        like = f"%{query.lower()}%"
        result = await self.session.execute(
            select(Team)
            .where(func.lower(Team.name).like(like))
            .options(
                selectinload(Team.members).selectinload(TeamMember.user),
                selectinload(Team.owner),
            )
        )
        return result.scalars().all()

    async def add_member_to_team(self, team: Team, user: User, role: str = "member") -> TeamMember:
        membership = TeamMember(team=team, user=user, role=role)
        self.session.add(membership)
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            raise ValueError("Участник уже состоит в команде")
        return membership

    async def remove_member_from_team(self, team: Team, user: User) -> None:
        await self.session.execute(
            delete(TeamMember).where(
                TeamMember.team_id == team.id, TeamMember.user_id == user.id
            )
        )
        await self.session.flush()

    async def delete_team(self, team: Team) -> None:
        await self.session.delete(team)
        await self.session.flush()

    async def set_team_photo(self, team: Team, file_id: str) -> None:
        team.photo_file_id = file_id
        await self.session.flush()

    # Event management
    async def list_events(self, only_open: bool = False) -> Sequence[Event]:
        stmt = select(Event).order_by(Event.start_at.asc())
        if only_open:
            now = datetime.utcnow()
            stmt = stmt.where(
                Event.registration_start <= now,
                Event.registration_end >= now,
            )
        result = await self.session.execute(
            stmt.options(
                selectinload(Event.registrations).selectinload(EventRegistration.user)
            )
        )
        return result.scalars().all()

    async def get_event(self, event_id: int) -> Optional[Event]:
        result = await self.session.execute(
            select(Event)
            .where(Event.id == event_id)
            .options(
                selectinload(Event.registrations).selectinload(EventRegistration.user)
            )
        )
        return result.scalar_one_or_none()

    async def create_event(
        self,
        *,
        title: str,
        description: Optional[str],
        location: Optional[str],
        registration_start: datetime,
        registration_end: datetime,
        start_at: datetime,
        end_at: datetime,
        capacity: Optional[int],
        admin_id: Optional[int] = None,
        template: Optional[str] = None,
    ) -> Event:
        self._validate_event_dates(
            registration_start,
            registration_end,
            start_at,
            end_at,
        )
        event = Event(
            title=title,
            description=description,
            location=location,
            registration_start=registration_start,
            registration_end=registration_end,
            start_at=start_at,
            end_at=end_at,
            capacity=capacity,
        )
        self.session.add(event)
        await self.session.flush()
        await self._log_event_change(
            event,
            action=EventChangeAction.CREATED,
            admin_id=admin_id,
            payload={
                "title": title,
                "start_at": start_at.isoformat(),
                "end_at": end_at.isoformat(),
                "template": template,
            },
        )
        return event

    async def update_event(
        self,
        event: Event,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        registration_start: Optional[datetime] = None,
        registration_end: Optional[datetime] = None,
        start_at: Optional[datetime] = None,
        end_at: Optional[datetime] = None,
        capacity: Optional[int] = None,
        admin_id: Optional[int] = None,
    ) -> Event:
        changes = {}
        if title is not None:
            event.title = title
            changes["title"] = title
        if description is not None:
            event.description = description
            changes["description"] = description
        if location is not None:
            event.location = location
            changes["location"] = location
        if registration_start is not None:
            event.registration_start = registration_start
            changes["registration_start"] = registration_start.isoformat()
        if registration_end is not None:
            event.registration_end = registration_end
            changes["registration_end"] = registration_end.isoformat()
        if start_at is not None:
            event.start_at = start_at
            changes["start_at"] = start_at.isoformat()
        if end_at is not None:
            event.end_at = end_at
            changes["end_at"] = end_at.isoformat()
        self._validate_event_dates(
            event.registration_start,
            event.registration_end,
            event.start_at,
            event.end_at,
        )
        if capacity is not None:
            event.capacity = capacity
            changes["capacity"] = capacity
        await self.session.flush()
        if changes:
            await self._log_event_change(
                event,
                action=EventChangeAction.UPDATED,
                admin_id=admin_id,
                payload=changes,
            )
        return event

    async def set_event_photo(self, event: Event, file_id: str, admin_id: Optional[int] = None) -> None:
        event.photo_file_id = file_id
        await self.session.flush()
        await self._log_event_change(
            event,
            action=EventChangeAction.PHOTO_UPDATED,
            admin_id=admin_id,
            payload={"photo_file_id": file_id},
        )

    async def delete_event(self, event: Event) -> None:
        await self.session.delete(event)
        await self.session.flush()

    async def register_for_event(self, event: Event, user: User) -> EventRegistration:
        if event.capacity is not None:
            reg_count = await self.session.scalar(
                select(func.count(EventRegistration.id)).where(
                    EventRegistration.event_id == event.id,
                    EventRegistration.status == RegistrationStatus.REGISTERED,
                )
            )
            if reg_count >= event.capacity:
                raise ValueError("Свободных мест нет")

        now = datetime.utcnow()
        if not (event.registration_start <= now <= event.registration_end):
            raise ValueError("Регистрация закрыта")

        existing = await self.session.execute(
            select(EventRegistration).where(
                EventRegistration.event_id == event.id,
                EventRegistration.user_id == user.id,
            )
        )
        registration = existing.scalar_one_or_none()
        if registration:
            if registration.status == RegistrationStatus.CANCELLED:
                registration.status = RegistrationStatus.REGISTERED
                await self.session.flush()
                await self._add_points(user, settings.points_per_event)
                return registration
            raise ValueError("Вы уже зарегистрированы")

        registration = EventRegistration(event=event, user=user)
        self.session.add(registration)
        await self.session.flush()

        await self._add_points(user, settings.points_per_event)
        return registration

    async def cancel_registration(self, event: Event, user: User) -> None:
        result = await self.session.execute(
            select(EventRegistration).where(
                EventRegistration.event_id == event.id,
                EventRegistration.user_id == user.id,
            )
        )
        registration = result.scalar_one_or_none()
        if not registration:
            raise ValueError("Вы не зарегистрированы")
        if registration.status == RegistrationStatus.CANCELLED:
            raise ValueError("Регистрация уже отменена")
        registration.status = RegistrationStatus.CANCELLED
        user.points = max(0, user.points - settings.points_per_event)
        await self.session.flush()

    async def list_user_registrations(self, user_id: int) -> Sequence[EventRegistration]:
        result = await self.session.execute(
            select(EventRegistration)
            .where(EventRegistration.user_id == user_id)
            .order_by(EventRegistration.created_at.desc())
            .options(selectinload(EventRegistration.event))
        )
        return result.scalars().all()

    async def search_events(self, query: str) -> Sequence[Event]:
        like = f"%{query.lower()}%"
        result = await self.session.execute(
            select(Event)
            .where(
                or_(
                    func.lower(Event.title).like(like),
                    func.lower(Event.description).like(like),
                )
            )
            .options(
                selectinload(Event.registrations).selectinload(EventRegistration.user)
            )
        )
        return result.scalars().all()

    async def upcoming_events_for_reminder(self) -> Sequence[Event]:
        now = datetime.utcnow()
        reminder_time = now + timedelta(hours=settings.reminder_hours_before)
        result = await self.session.execute(
            select(Event)
            .where(
                Event.start_at <= reminder_time,
                Event.start_at >= now,
                or_(Event.reminder_sent_at.is_(None), Event.reminder_sent_at < Event.start_at),
            )
            .order_by(Event.start_at.asc())
            .options(
                selectinload(Event.registrations).selectinload(EventRegistration.user)
            )
        )
        return result.scalars().all()

    async def mark_event_reminded(self, event: Event) -> None:
        event.reminder_sent_at = datetime.utcnow()
        await self.session.flush()

    async def get_event_logs(self, event_id: int, limit: int = 20) -> Sequence[EventChangeLog]:
        result = await self.session.execute(
            select(EventChangeLog)
            .where(EventChangeLog.event_id == event_id)
            .order_by(EventChangeLog.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_application_logs(self, application_id: int) -> Sequence[ApplicationDecisionLog]:
        result = await self.session.execute(
            select(ApplicationDecisionLog)
            .where(ApplicationDecisionLog.application_id == application_id)
            .order_by(ApplicationDecisionLog.created_at.desc())
        )
        return result.scalars().all()

    @staticmethod
    def _validate_event_dates(
        registration_start: datetime,
        registration_end: datetime,
        start_at: datetime,
        end_at: datetime,
    ) -> None:
        if registration_start > registration_end:
            raise ValueError(
                "Дата окончания регистрации не может быть раньше даты начала регистрации."
            )
        if start_at > end_at:
            raise ValueError(
                "Окончание мероприятия не может быть раньше его начала."
            )
        if registration_end > start_at:
            raise ValueError(
                "Регистрация должна завершиться до начала мероприятия."
            )

    async def _log_event_change(
        self,
        event: Event,
        *,
        action: EventChangeAction,
        admin_id: Optional[int],
        payload: Optional[dict] = None,
    ) -> None:
        if not admin_id:
            return
        log = EventChangeLog(
            event=event,
            admin_id=admin_id,
            action=action,
            payload=json.dumps(payload, ensure_ascii=False) if payload else None,
        )
        self.session.add(log)
        await self.session.flush()

    async def _log_application_decision(
        self,
        application: Application,
        decision: ApplicationDecisionType,
        *,
        admin_id: Optional[int],
        comment: Optional[str],
    ) -> None:
        if not admin_id:
            return
        log = ApplicationDecisionLog(
            application=application,
            admin_id=admin_id,
            decision=decision,
            comment=comment,
        )
        self.session.add(log)
        await self.session.flush()

    # Statistics and exports
    async def get_statistics(self) -> dict:
        users_total = await self.session.scalar(select(func.count(User.id))) or 0
        members_active = await self.session.scalar(
            select(func.count(User.id)).where(User.status == MembershipStatus.ACTIVE)
        ) or 0
        applications_pending = await self.session.scalar(
            select(func.count(Application.id)).where(
                Application.status == ApplicationStatus.PENDING
            )
        ) or 0
        teams_total = await self.session.scalar(select(func.count(Team.id))) or 0
        events_total = await self.session.scalar(select(func.count(Event.id))) or 0
        upcoming = await self.session.scalar(
            select(func.count(Event.id)).where(Event.start_at >= datetime.utcnow())
        ) or 0
        registrations_total = await self.session.scalar(
            select(func.count(EventRegistration.id)).where(
                EventRegistration.status == RegistrationStatus.REGISTERED
            )
        ) or 0
        return {
            "users_total": users_total,
            "members_active": members_active,
            "applications_pending": applications_pending,
            "teams_total": teams_total,
            "events_total": events_total,
            "upcoming_events": upcoming,
            "event_registrations": registrations_total,
        }

    async def export_users_csv(self, path: Path) -> Path:
        users = await self.session.execute(select(User).order_by(User.full_name.asc()))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.writer(fp)
            writer.writerow(
                [
                    "ID",
                    "Telegram ID",
                    "Имя",
                    "Username",
                    "Email",
                    "Телефон",
                    "Статус",
                    "Баллы",
                ]
            )
            for user in users.scalars():
                writer.writerow(
                    [
                        user.id,
                        user.telegram_id,
                        user.full_name,
                        user.username or "",
                        user.email,
                        user.phone or "",
                        user.status.value,
                        user.points,
                    ]
                )
        return path

    async def export_users_xlsx(self, path: Path) -> Path:
        users = await self.session.execute(select(User).order_by(User.full_name.asc()))
        workbook: Workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Участники"
        sheet.append(
            [
                "ID",
                "Telegram ID",
                "Имя",
                "Username",
                "Email",
                "Телефон",
                "Статус",
                "Баллы",
            ]
        )
        for user in users.scalars():
            sheet.append(
                [
                    user.id,
                    user.telegram_id,
                    user.full_name,
                    user.username or "",
                    user.email,
                    user.phone or "",
                    user.status.value,
                    user.points,
                ]
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(path)
        return path

    async def export_teams_csv(self, path: Path) -> Path:
        teams = await self.session.execute(
            select(Team)
            .order_by(Team.name.asc())
            .options(
                selectinload(Team.members).selectinload(TeamMember.user),
                selectinload(Team.owner),
            )
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.writer(fp)
            writer.writerow(
                [
                    "Команда",
                    "Постоянная",
                    "Капитан",
                    "Участники",
                ]
            )
            for team in teams.scalars():
                members = ", ".join(member.user.full_name for member in team.members)
                writer.writerow(
                    [
                        team.name,
                        "Да" if team.is_permanent else "Нет",
                        team.owner.full_name,
                        members,
                    ]
                )
        return path

    async def export_teams_xlsx(self, path: Path) -> Path:
        teams = await self.session.execute(
            select(Team)
            .order_by(Team.name.asc())
            .options(
                selectinload(Team.members).selectinload(TeamMember.user),
                selectinload(Team.owner),
            )
        )
        workbook: Workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Команды"
        sheet.append(["Команда", "Постоянная", "Капитан", "Участники"])
        for team in teams.scalars():
            members = ", ".join(member.user.full_name for member in team.members)
            sheet.append(
                [
                    team.name,
                    "Да" if team.is_permanent else "Нет",
                    team.owner.full_name,
                    members,
                ]
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(path)
        return path

    async def _add_points(self, user: User, points: int) -> None:
        user.points += points
        await self.session.flush()
        await self._assign_achievements(user)

    async def _assign_achievements(self, user: User) -> None:
        thresholds = [50, 150, 300]
        existing = await self.session.execute(
            select(UserAchievement).where(UserAchievement.user_id == user.id)
        )
        owned_codes = {
            ach.achievement.code
            for ach in existing.scalars()
        }
        for threshold in thresholds:
            code = f"points_{threshold}"
            if user.points >= threshold and code not in owned_codes:
                achievement = await self.session.scalar(
                    select(Achievement).where(Achievement.code == code)
                )
                if not achievement:
                    achievement = Achievement(
                        code=code,
                        title=f"{threshold} баллов",
                        description="Набрано достаточно баллов за участие",
                        points_required=threshold,
                    )
                    self.session.add(achievement)
                    await self.session.flush()
                award = UserAchievement(user=user, achievement=achievement)
                self.session.add(award)
        await self.session.flush()


async def ensure_default_achievements(session: AsyncSession) -> None:
    defaults = [
        ("points_50", "50 баллов", "Отличный старт", 50),
        ("points_150", "150 баллов", "Активный участник", 150),
        ("points_300", "300 баллов", "Легенда клуба", 300),
    ]
    for code, title, description, points in defaults:
        exists = await session.scalar(select(Achievement).where(Achievement.code == code))
        if not exists:
            session.add(
                Achievement(
                    code=code,
                    title=title,
                    description=description,
                    points_required=points,
                )
            )
    await session.commit()
