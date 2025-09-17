from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
_engine = create_async_engine(_settings.database_url, echo=False)
AsyncSessionMaker = async_sessionmaker(_engine, expire_on_commit=False)


async def init_db() -> None:
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_columns(conn)


async def _ensure_columns(conn) -> None:
    if not _settings.database_url.startswith("sqlite"):
        return

    async def column_exists(table: str, column: str) -> bool:
        result = await conn.exec_driver_sql(f"PRAGMA table_info({table})")
        return any(row[1] == column for row in result.fetchall())

    async def add_column(table: str, column: str, definition: str) -> None:
        await conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    if not await column_exists("users", "photo_file_id"):
        await add_column("users", "photo_file_id", "TEXT")
    if not await column_exists("teams", "photo_file_id"):
        await add_column("teams", "photo_file_id", "TEXT")
    if not await column_exists("events", "photo_file_id"):
        await add_column("events", "photo_file_id", "TEXT")
    if not await column_exists("users", "group_name"):
        await add_column("users", "group_name", "TEXT")


@asynccontextmanager
async def session_scope() -> AsyncSession:
    session: AsyncSession = AsyncSessionMaker()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
