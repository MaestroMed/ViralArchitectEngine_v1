"""Database configuration and session management."""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from forge_engine.core.config import settings

logger = logging.getLogger(__name__)

# Create async engine
DATABASE_URL = f"sqlite+aiosqlite:///{settings.DATABASE_PATH}"
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Disabled SQL echo to avoid flooding logs and blocking requests
    future=True,
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""
    pass


async def init_db() -> None:
    """Initialize the database, creating tables if needed.

    Kept for zero-config first boot. Schema *versioning* lives in Alembic
    (see ``alembic/`` + ``tests/test_migrations.py``); for an existing DB,
    ``alembic stamp head`` then ``alembic upgrade head`` is the upgrade path.
    ``create_all`` is additive (never drops), so it coexists safely.
    """
    # Import all models so their tables are registered with Base.metadata
    from forge_engine.models import (  # noqa: F401
        api_key,
        artifact,
        channel,
        device_token,
        job,
        profile,
        project,
        review,
        segment,
        template,
        training_data,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created/verified")


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
    logger.info("Database connections closed")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()









