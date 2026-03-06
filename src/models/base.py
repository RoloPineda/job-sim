"""SQLAlchemy declarative base and shared column definitions."""

import uuid

from sqlalchemy import Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models.

    All model classes inherit from this to register with a single
    metadata instance that Alembic uses for migration autogeneration.
    """


class UUIDPrimaryKeyMixin:
    """Mixin that adds a UUID primary key with auto-generation.

    Attributes:
        id: Auto-generated UUID v4 primary key.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )