"""ORM model for simulation run configuration."""

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, UUIDPrimaryKeyMixin

_VALID_RUN_STATUSES = ("pending", "running", "completed", "failed")


class SimulationRun(UUIDPrimaryKeyMixin, Base):
    """A single simulation run and its frozen configuration.

    Every other table references this via ``run_id`` to scope data
    to a specific simulation execution.

    Attributes:
        config: Complete RunConfig parameters stored as a JSONB blob.
        status: Current state of the run lifecycle.
        created_at: Timestamp when the run was created.
    """

    __tablename__ = "simulation_runs"
    __table_args__ = (
        CheckConstraint(
            f"status IN {_VALID_RUN_STATUSES!r}",
            name="ck_simulation_runs_status",
        ),
    )

    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
