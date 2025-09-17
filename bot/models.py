from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class MembershipStatus(str, Enum):
    NEW = "new"
    ACTIVE = "active"
    REJECTED = "rejected"
    LEFT = "left"


class ApplicationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RegistrationStatus(str, Enum):
    REGISTERED = "registered"
    CANCELLED = "cancelled"


class EventChangeAction(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    PHOTO_UPDATED = "photo_updated"


class ApplicationDecisionType(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(128), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    profession: Mapped[Optional[str]] = mapped_column(String(128))
    company: Mapped[Optional[str]] = mapped_column(String(128))
    group_name: Mapped[Optional[str]] = mapped_column(String(64))
    status: Mapped[MembershipStatus] = mapped_column(
        SAEnum(MembershipStatus), default=MembershipStatus.NEW, nullable=False
    )
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    email_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(256))

    application: Mapped[Optional[Application]] = relationship(
        "Application", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    teams: Mapped[List[TeamMember]] = relationship(
        "TeamMember", back_populates="user", cascade="all, delete-orphan"
    )
    registrations: Mapped[List[EventRegistration]] = relationship(
        "EventRegistration", back_populates="user", cascade="all, delete-orphan"
    )
    achievements: Mapped[List[UserAchievement]] = relationship(
        "UserAchievement", back_populates="user", cascade="all, delete-orphan"
    )


class Application(Base, TimestampMixin):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    status: Mapped[ApplicationStatus] = mapped_column(
        SAEnum(ApplicationStatus), default=ApplicationStatus.PENDING, nullable=False
    )
    motivation: Mapped[Optional[str]] = mapped_column(Text)
    comment: Mapped[Optional[str]] = mapped_column(Text)
    decision_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship("User", back_populates="application")
    decision_logs: Mapped[List[ApplicationDecisionLog]] = relationship(
        "ApplicationDecisionLog",
        cascade="all, delete-orphan",
        order_by="ApplicationDecisionLog.created_at",
        overlaps="application",
    )


class Team(Base, TimestampMixin):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_permanent: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(256))

    owner: Mapped[User] = relationship("User", foreign_keys=[owner_id])
    members: Mapped[List[TeamMember]] = relationship(
        "TeamMember", back_populates="team", cascade="all, delete-orphan"
    )


class TeamMember(Base, TimestampMixin):
    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="member", nullable=False)

    team: Mapped[Team] = relationship("Team", back_populates="members")
    user: Mapped[User] = relationship("User", back_populates="teams")


class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    location: Mapped[Optional[str]] = mapped_column(String(256))
    registration_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    registration_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    capacity: Mapped[Optional[int]] = mapped_column(Integer)
    reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(256))

    __table_args__ = (
        CheckConstraint("registration_start <= registration_end", name="ck_registration_window"),
        CheckConstraint("start_at <= end_at", name="ck_event_duration"),
    )

    registrations: Mapped[List[EventRegistration]] = relationship(
        "EventRegistration", back_populates="event", cascade="all, delete-orphan"
    )
    change_logs: Mapped[List[EventChangeLog]] = relationship(
        "EventChangeLog", back_populates="event", cascade="all, delete-orphan"
    )


class EventRegistration(Base, TimestampMixin):
    __tablename__ = "event_registrations"
    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_event_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[RegistrationStatus] = mapped_column(
        SAEnum(RegistrationStatus), default=RegistrationStatus.REGISTERED, nullable=False
    )
    attended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    event: Mapped[Event] = relationship("Event", back_populates="registrations")
    user: Mapped[User] = relationship("User", back_populates="registrations")


class Achievement(Base, TimestampMixin):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    points_required: Mapped[int] = mapped_column(Integer, nullable=False)

    user_achievements: Mapped[List[UserAchievement]] = relationship(
        "UserAchievement", back_populates="achievement", cascade="all, delete-orphan"
    )


class UserAchievement(Base, TimestampMixin):
    __tablename__ = "user_achievements"
    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    achievement_id: Mapped[int] = mapped_column(
        ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False
    )

    user: Mapped[User] = relationship("User", back_populates="achievements")
    achievement: Mapped[Achievement] = relationship("Achievement", back_populates="user_achievements")


class EventChangeLog(Base, TimestampMixin):
    __tablename__ = "event_change_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    admin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[EventChangeAction] = mapped_column(SAEnum(EventChangeAction), nullable=False)
    payload: Mapped[Optional[str]] = mapped_column(Text)

    event: Mapped[Event] = relationship("Event", back_populates="change_logs")


class ApplicationDecisionLog(Base, TimestampMixin):
    __tablename__ = "application_decision_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    admin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[ApplicationDecisionType] = mapped_column(
        SAEnum(ApplicationDecisionType), nullable=False
    )
    comment: Mapped[Optional[str]] = mapped_column(Text)

    application: Mapped[Application] = relationship("Application", overlaps="decision_logs")
