from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    bot_token: str = Field(..., alias="BOT_TOKEN")
    admin_ids: List[int] = Field(default_factory=list, alias="ADMIN_IDS")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./bot.db",
        alias="DATABASE_URL",
    )
    smtp_host: Optional[str] = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: Optional[str] = Field(default=None, alias="SMTP_USER")
    smtp_password: Optional[str] = Field(default=None, alias="SMTP_PASSWORD")
    smtp_from: Optional[str] = Field(default=None, alias="SMTP_FROM")
    reminder_hours_before: int = Field(default=24, alias="REMINDER_HOURS_BEFORE")
    points_per_event: int = Field(default=10, alias="POINTS_PER_EVENT")
    timezone: str = Field(default="Europe/Moscow", alias="TIMEZONE")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: Union[str, List[int], int]) -> List[int]:
        if isinstance(value, list):
            return [int(v) for v in value]
        if isinstance(value, str):
            cleaned = [v.strip() for v in value.replace(";", ",").split(",")]
            return [int(v) for v in cleaned if v]
        if isinstance(value, int):
            return [value]
        return []

    @property
    def has_smtp_credentials(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password and self.smtp_from)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
