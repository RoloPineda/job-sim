"""ORM models for companies and job postings."""

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, UUIDPrimaryKeyMixin

_VALID_INDUSTRIES = (
    "technology", "finance", "healthcare", "retail",
    "media", "education", "manufacturing", "consulting",
)
_VALID_COMPANY_SIZES = ("startup", "mid", "enterprise")
_VALID_GROWTH_STAGES = ("early", "scaling", "mature")
_VALID_BUDGET_FLEXIBILITIES = ("rigid", "moderate", "flexible")
_VALID_RESPONSIVENESS_PATTERNS = ("fast", "slow", "unpredictable", "ghosts")
_VALID_REJECTION_SPECIFICITIES = ("high", "moderate", "low")
_VALID_SENIORITIES = ("junior", "mid", "senior", "lead", "staff")
_VALID_POSTING_STATUSES = ("open", "closed", "filled", "expired")


class Company(UUIDPrimaryKeyMixin, Base):
    """A company's identity and hiring behavior for the simulation.

    Immutable for the duration of a simulation run.

    Attributes:
        run_id: Simulation run this company belongs to.
        name: Company name.
        industry: Sector the company operates in.
        size: Scale of the company.
        growth_stage: Where the company is in its lifecycle.
        culture_description: Freeform text describing company culture.
        budget_flexibility: How much room for compensation negotiation.
        responsiveness_pattern: How the company typically responds.
        base_response_delay: Rounds before the company typically responds.
        response_delay_variance: Randomness range added to base delay.
        rejection_specificity: Detail level in rejection communications.
        recruiters: Recruiters employed by this company.
        hiring_managers: Hiring managers employed by this company.
        postings: Job postings published by this company.
    """

    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint(
            f"industry IN {_VALID_INDUSTRIES!r}",
            name="ck_companies_industry",
        ),
        CheckConstraint(
            f"size IN {_VALID_COMPANY_SIZES!r}",
            name="ck_companies_size",
        ),
        CheckConstraint(
            f"growth_stage IN {_VALID_GROWTH_STAGES!r}",
            name="ck_companies_growth_stage",
        ),
        CheckConstraint(
            f"budget_flexibility IN {_VALID_BUDGET_FLEXIBILITIES!r}",
            name="ck_companies_budget_flexibility",
        ),
        CheckConstraint(
            f"responsiveness_pattern IN {_VALID_RESPONSIVENESS_PATTERNS!r}",
            name="ck_companies_responsiveness_pattern",
        ),
        CheckConstraint(
            f"rejection_specificity IN {_VALID_REJECTION_SPECIFICITIES!r}",
            name="ck_companies_rejection_specificity",
        ),
        CheckConstraint(
            "base_response_delay >= 1",
            name="ck_companies_base_response_delay",
        ),
        CheckConstraint(
            "response_delay_variance >= 0",
            name="ck_companies_response_delay_variance",
        ),
        CheckConstraint(
            "response_delay_variance < base_response_delay",
            name="ck_companies_variance_lt_delay",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("simulation_runs.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    industry: Mapped[str] = mapped_column(String(20), nullable=False)
    size: Mapped[str] = mapped_column(String(20), nullable=False)
    growth_stage: Mapped[str] = mapped_column(String(20), nullable=False)
    culture_description: Mapped[str] = mapped_column(Text, nullable=False)
    budget_flexibility: Mapped[str] = mapped_column(String(20), nullable=False)
    responsiveness_pattern: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    base_response_delay: Mapped[int] = mapped_column(Integer, nullable=False)
    response_delay_variance: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    rejection_specificity: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    recruiters: Mapped[list["Recruiter"]] = relationship(
        back_populates="company"
    )
    hiring_managers: Mapped[list["HiringManager"]] = relationship(
        back_populates="company"
    )
    postings: Mapped[list["JobPosting"]] = relationship(
        back_populates="company"
    )


class JobPosting(UUIDPrimaryKeyMixin, Base):
    """A job listing on the simulation's job board.

    Contains both visible attributes that jobseekers can see and hidden
    attributes (``is_ghost``, ``actual_budget``) used only by the engine.

    Attributes:
        run_id: Simulation run this posting belongs to.
        company_id: Company that owns this posting.
        hiring_manager_id: Hiring manager responsible for this role.
        recruiter_id: Recruiter assigned to manage this posting.
        title: Job title as displayed to seekers.
        department: Team or org the role sits in.
        description: Freeform job description visible to seekers.
        requirements: Stated requirements seekers evaluate against.
        salary_range_low: Bottom of posted salary range, or None if
            undisclosed.
        salary_range_high: Top of posted salary range, or None if
            undisclosed.
        location: Where the role is based.
        remote: Whether the role is remote.
        seniority: Level of the role.
        round_posted: Simulation round when the posting went live.
        round_expires: Round when posting comes off the board, or None.
        status: Current lifecycle state of the posting.
        is_ghost: If true, the posting never advances anyone.
        actual_budget: Real budget that may differ from posted range.
        company: The company that owns this posting.
        hiring_manager: The hiring manager for this role.
        recruiter: The recruiter assigned to this posting.
    """

    __tablename__ = "job_postings"
    __table_args__ = (
        CheckConstraint(
            f"seniority IN {_VALID_SENIORITIES!r}",
            name="ck_job_postings_seniority",
        ),
        CheckConstraint(
            f"status IN {_VALID_POSTING_STATUSES!r}",
            name="ck_job_postings_status",
        ),
        CheckConstraint(
            "round_posted >= 0",
            name="ck_job_postings_round_posted",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("simulation_runs.id"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id"), nullable=False
    )
    hiring_manager_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agents.id"), nullable=False
    )
    recruiter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agents.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    department: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirements: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False
    )
    salary_range_low: Mapped[int | None] = mapped_column(Integer)
    salary_range_high: Mapped[int | None] = mapped_column(Integer)
    location: Mapped[str] = mapped_column(String, nullable=False)
    remote: Mapped[bool] = mapped_column(Boolean, nullable=False)
    seniority: Mapped[str] = mapped_column(String(20), nullable=False)
    round_posted: Mapped[int] = mapped_column(Integer, nullable=False)
    round_expires: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="open"
    )
    is_ghost: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    actual_budget: Mapped[int | None] = mapped_column(Integer)

    company: Mapped["Company"] = relationship(back_populates="postings")
    hiring_manager: Mapped["HiringManager"] = relationship(
        back_populates="managed_postings",
        foreign_keys=[hiring_manager_id],
    )
    recruiter: Mapped["Recruiter"] = relationship(
        back_populates="assigned_postings",
        foreign_keys=[recruiter_id],
    )
