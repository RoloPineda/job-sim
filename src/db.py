"""Database connection module.

Provides sync and async SQLAlchemy engines and session factories,
plus context managers for convenient session lifecycle management.
"""

import os
from collections.abc import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://jobsim:jobsim@localhost:5433/jobsim",
)

# Detect if the driver substitution was a no-op, meaning the
# original URL uses an unexpected format
_default_async_url = DATABASE_URL.replace("postgresql+psycopg", "postgresql+asyncpg", 1)
if _default_async_url == DATABASE_URL and "asyncpg" not in DATABASE_URL:
    raise ValueError(
        "Cannot derive async URL from DATABASE_URL "
        f"({DATABASE_URL!r}). Set ASYNC_DATABASE_URL explicitly."
    )
ASYNC_DATABASE_URL = os.getenv("ASYNC_DATABASE_URL", _default_async_url)

engine = create_engine(DATABASE_URL)
async_engine = create_async_engine(ASYNC_DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)
AsyncSessionLocal = async_sessionmaker(bind=async_engine)


def get_session() -> Generator[Session, None, None]:
    """Provide a transactional sync session scope.

    Yields:
        A SQLAlchemy sync session that auto-commits on success
        and rolls back on exception.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional async session scope.

    Yields:
        A SQLAlchemy async session that auto-commits on success
        and rolls back on exception.
    """
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
