"""Async SQLAlchemy engine/session plumbing."""
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncSession, async_engine_from_config, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

from app.core.config import get_settings


class UTCDateTime(TypeDecorator):
    """Timezone-aware datetimes on every backend (SQLite drops tzinfo)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC) if value is not None else None

    def process_result_value(self, value: datetime | None, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


class Base(DeclarativeBase):
    pass


def _make_engine():
    s = get_settings()
    cfg = {"sqlalchemy.url": s.database_url}
    engine = async_engine_from_config(cfg, prefix="sqlalchemy.", pool_pre_ping=True)
    return engine


engine = _make_engine()
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all() -> None:
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
