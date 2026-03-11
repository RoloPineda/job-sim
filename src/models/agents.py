"""ORM models for simulation agents using joined-table inheritance."""

import uuid
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, UUIDPrimaryKeyMixin

_VALID_AGENT_TYPES = ("job_seeker", "recruiter", "hiring_manager")
_VALID_SELF_AWARENESS = ("accurate", "overconfident", "underconfident")
_VALID_COMMUNICATION_ABILITY = ("strong", "average", "weak")
_VALID_SENIORITIES = ("junior", "mid", "senior", "lead", "staff")
_VALID_LOCATION_FLEXIBILITY = ("rigid", "moderate", "flexible")
_VALID_REMOTE_PREFERENCE = ("remote_only", "hybrid", "onsite", "no_preference")
_VALID_EXPERIENCE_LEVELS = ("junior", "mid", "senior")
_VALID_TEAM_SITUATIONS = ("understaffed", "stable", "growing", "rebuilding")
_VALID_MANAGEMENT_STYLES = (
    "detailed_feedback",
    "vague",
    "responsive",
    "slow",
    "micromanager",
)
_VALID_FEEDBACK_CLARITY = ("clear", "vague", "contradictory")


class Agent(UUIDPrimaryKeyMixin, Base):
    """Base agent table for joined-table inheritance.

    Shared columns for all agent types. The ``agent_type`` column acts
    as the polymorphic discriminator. This class is never instantiated
    directly; use one of the concrete subclasses instead.

    Attributes:
        run_id: Simulation run this agent belongs to.
        agent_type: Discriminator for polymorphic identity.
        name: Display name.
        disposition: Personality traits that shape decision-making.
        backstory: Background narrative seeded at creation.
        location: Where the agent is based.
        state: Current mutable AgentState as JSONB.
    """

    __tablename__ = "agents"
    __table_args__ = (
        CheckConstraint(
            f"agent_type IN {_VALID_AGENT_TYPES!r}",
            name="ck_agents_agent_type",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("simulation_runs.id"), nullable=False
    )
    agent_type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    disposition: Mapped[str] = mapped_column(Text, nullable=False)
    backstory: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    __mapper_args__ = {
        "polymorphic_on": "agent_type",
    }


class JobSeeker(Agent):
    """Jobseeker agent with skills, preferences, and financial state.

    ``education_history`` and ``work_history`` are stored as JSONB
    since they are value objects without independent identity.

    Attributes:
        education_history: Academic background as a list of dicts.
        actual_skills: Ground truth skills, hidden from the agent.
        work_history: Past roles as a list of dicts.
        experience_years: Total years of professional experience.
        perceived_skills: Skills the agent believes it has.
        self_awareness: How accurately the agent assesses itself.
        communication_ability: How effectively the agent communicates.
        target_roles: Role titles the agent is searching for.
        target_seniority: Desired seniority level.
        target_comp_low: Minimum acceptable compensation in dollars.
        target_comp_high: Ideal compensation target in dollars.
        location_flexibility: Willingness to relocate.
        remote_preference: Preference for remote, hybrid, or onsite.
        savings: Dollar savings that deplete over rounds.
        burn_rate: How much the agent spends per round.
    """

    __tablename__ = "job_seekers"
    __table_args__ = (
        CheckConstraint(
            f"self_awareness IN {_VALID_SELF_AWARENESS!r}",
            name="ck_job_seekers_self_awareness",
        ),
        CheckConstraint(
            f"communication_ability IN {_VALID_COMMUNICATION_ABILITY!r}",
            name="ck_job_seekers_communication_ability",
        ),
        CheckConstraint(
            f"target_seniority IN {_VALID_SENIORITIES!r}",
            name="ck_job_seekers_target_seniority",
        ),
        CheckConstraint(
            f"location_flexibility IN {_VALID_LOCATION_FLEXIBILITY!r}",
            name="ck_job_seekers_location_flexibility",
        ),
        CheckConstraint(
            f"remote_preference IN {_VALID_REMOTE_PREFERENCE!r}",
            name="ck_job_seekers_remote_preference",
        ),
        CheckConstraint(
            "experience_years >= 0",
            name="ck_job_seekers_experience_years",
        ),
        CheckConstraint(
            "target_comp_low >= 0",
            name="ck_job_seekers_target_comp_low",
        ),
        CheckConstraint(
            "target_comp_high >= 0",
            name="ck_job_seekers_target_comp_high",
        ),
        CheckConstraint(
            "target_comp_low <= target_comp_high",
            name="ck_job_seekers_comp_range",
        ),
        CheckConstraint(
            "savings >= 0",
            name="ck_job_seekers_savings",
        ),
        CheckConstraint(
            "burn_rate > 0",
            name="ck_job_seekers_burn_rate",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agents.id"), primary_key=True
    )
    education_history: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    actual_skills: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    work_history: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    experience_years: Mapped[int] = mapped_column(Integer, nullable=False)
    perceived_skills: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    self_awareness: Mapped[str] = mapped_column(String(20), nullable=False)
    communication_ability: Mapped[str] = mapped_column(String(20), nullable=False)
    target_roles: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    target_seniority: Mapped[str] = mapped_column(String(20), nullable=False)
    target_comp_low: Mapped[int] = mapped_column(Integer, nullable=False)
    target_comp_high: Mapped[int] = mapped_column(Integer, nullable=False)
    location_flexibility: Mapped[str] = mapped_column(String(20), nullable=False)
    remote_preference: Mapped[str] = mapped_column(String(20), nullable=False)
    savings: Mapped[int] = mapped_column(Integer, nullable=False)
    burn_rate: Mapped[int] = mapped_column(Integer, nullable=False)

    __mapper_args__ = {"polymorphic_identity": "job_seeker"}


class Recruiter(Agent):
    """Recruiter agent linked to a company.

    Posting assignments are modeled as a ``recruiter_id`` FK on
    ``job_postings``. Hiring manager associations are derived through
    shared postings rather than stored directly.

    Attributes:
        company_id: The company this recruiter works for.
        experience_level: General recruiter competence level.
        current_workload: Number of open roles currently managed.
        company: The company this recruiter belongs to.
        assigned_postings: Job postings assigned to this recruiter.
    """

    __tablename__ = "recruiters"
    __table_args__ = (
        CheckConstraint(
            f"experience_level IN {_VALID_EXPERIENCE_LEVELS!r}",
            name="ck_recruiters_experience_level",
        ),
        CheckConstraint(
            "current_workload >= 0",
            name="ck_recruiters_current_workload",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agents.id"), primary_key=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id"), nullable=False
    )
    experience_level: Mapped[str] = mapped_column(String(20), nullable=False)
    current_workload: Mapped[int] = mapped_column(Integer, nullable=False)

    company: Mapped["Company"] = relationship(back_populates="recruiters")
    assigned_postings: Mapped[list["JobPosting"]] = relationship(
        back_populates="recruiter",
        foreign_keys="JobPosting.recruiter_id",
    )

    __mapper_args__ = {"polymorphic_identity": "recruiter"}


class HiringManager(Agent):
    """Hiring manager agent linked to a company.

    Attributes:
        company_id: The company this hiring manager belongs to.
        team_size: Current size of the hiring manager's team.
        team_situation: State of the team affecting hiring urgency.
        management_style: How the manager interacts with candidates.
        technical_bar: What the manager values in candidates.
        interview_capacity_per_round: Max interviews per round.
        past_hiring_description: Context about previous hires.
        feedback_clarity: How clearly the manager communicates
            expectations.
        company: The company this hiring manager belongs to.
        managed_postings: Job postings this manager is responsible for.
    """

    __tablename__ = "hiring_managers"
    __table_args__ = (
        CheckConstraint(
            f"team_situation IN {_VALID_TEAM_SITUATIONS!r}",
            name="ck_hiring_managers_team_situation",
        ),
        CheckConstraint(
            f"management_style IN {_VALID_MANAGEMENT_STYLES!r}",
            name="ck_hiring_managers_management_style",
        ),
        CheckConstraint(
            f"feedback_clarity IN {_VALID_FEEDBACK_CLARITY!r}",
            name="ck_hiring_managers_feedback_clarity",
        ),
        CheckConstraint(
            "team_size >= 0",
            name="ck_hiring_managers_team_size",
        ),
        CheckConstraint(
            "interview_capacity_per_round >= 0",
            name="ck_hiring_managers_interview_capacity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agents.id"), primary_key=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id"), nullable=False
    )
    team_size: Mapped[int] = mapped_column(Integer, nullable=False)
    team_situation: Mapped[str] = mapped_column(String(20), nullable=False)
    management_style: Mapped[str] = mapped_column(String(20), nullable=False)
    technical_bar: Mapped[str] = mapped_column(Text, nullable=False)
    interview_capacity_per_round: Mapped[int] = mapped_column(Integer, nullable=False)
    past_hiring_description: Mapped[str] = mapped_column(Text, nullable=False)
    feedback_clarity: Mapped[str] = mapped_column(String(20), nullable=False)

    company: Mapped["Company"] = relationship(back_populates="hiring_managers")
    managed_postings: Mapped[list["JobPosting"]] = relationship(
        back_populates="hiring_manager",
        foreign_keys="JobPosting.hiring_manager_id",
    )

    __mapper_args__ = {"polymorphic_identity": "hiring_manager"}
