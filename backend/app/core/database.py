"""
Database setup - SQLAlchemy async engine and session.

- Base dùng naming_convention trùng quy ước pk_/fk_/uq_/ck_/ix_ của DB (doc 05 §6.2).
- KHÔNG gọi Base.metadata.create_all(): lược đồ do database/postgresql/ và Alembic quản lý.
- get_db KHÔNG tự commit: ranh giới transaction nằm ở service (doc 05 §6.1).
"""

from collections.abc import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency: một session cho mỗi request. Service tự commit; lỗi thì rollback."""
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
