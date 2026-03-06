"""Agent profile and state schemas."""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator, ConfigDict
from schemas.types import AgentType


class AgentProfile(BaseModel):
    """Stable identity and disposition for a simulation agent.

    These attributes are immutable since they don't change over the course of a job search.

    Attributes:
        id: Unique agent identifier.
        agent_type: The role this agent plays in the simulation.
        name: Display name.
        disposition: Personality traits that shape decision-making.
        backstory: Background narrative seeded at creation, never modified.
        location: Where the agent is based.
    """

    model_config = ConfigDict(frozen=True)
    id: str
    agent_type: AgentType
    name: str
    disposition: str
    backstory: str  # Fed into system prompt to anchor persona across rounds
    location: str


class JobSeekerProfile(AgentProfile):
    """A jobseeker's profile including skills, preferences, and traits.

    The agent builds its own resume from perceived_skills, work_history,
    education, and projects. actual_skills is hidden from the agent and
    used only for post-simulation analysis.

    Attributes:
        education_history: Academic background (e.g., HS, BS, MS, PhD).
        actual_skills: Ground truth skills, never included in agent prompts.
        experience_years: Total years of professional experience.
        work_history: Past roles with accomplishments for resume building.
        perceived_skills: Skills the agent believes it has.
        self_awareness: How accurately the agent assesses its own abilities.
        communication_ability: How effectively the agent communicates.
        target_roles: Role titles the agent is searching for.
        target_seniority: Desired seniority level.
        target_comp_low: Minimum acceptable compensation in dollars.
        target_comp_high: Ideal compensation target in dollars.
        location_flexibility: Willingness to relocate.
        remote_preference: Preference for remote, hybrid, or onsite work.
        savings: Dollar savings that deplete over rounds.
        monthly_expenses: How much the agent spends per round. Round intervals can represent different timelines
                        (daily, weekly, monthly) and they are defined in the simulation config.
    """

    # Identity (treat as immutable)
    education_history: list[Education]
    actual_skills: list[str]  # Hidden from agent, used for post-simulation analysis
    work_history: list[WorkEntry] = Field(min_length=0)
    experience_years: int = Field(ge=0)

    # self-perception (treat as immutable)
    perceived_skills: list[str]
    self_awareness: Literal["accurate", "overconfident", "underconfident"]
    communication_ability: Literal["strong", "average", "weak"]

    # Preferences (mutable)
    target_roles: list[str] = Field(min_length=1)
    target_seniority: Literal["junior", "mid", "senior", "lead", "staff"]
    target_comp_low: int = Field(ge=0)
    target_comp_high: int = Field(ge=0)
    location_flexibility: Literal["rigid", "moderate", "flexible"]
    remote_preference: Literal["remote_only", "hybrid", "onsite", "no_preference"]

    # Financial (mutable)
    savings: int = Field(ge=0)  # Depletes over rounds, creating behavioral pressure
    burn_rate: int = Field(gt=0)  # gt=0 prevents division by zero



    @model_validator(mode="after")
    def validate_comp_range(self) -> "JobSeekerProfile":
        """Ensure target_comp_low does not exceed target_comp_high."""
        if self.target_comp_low > self.target_comp_high:
            raise ValueError(
                f"target_comp_low ({self.target_comp_low}) must not exceed "
                f"target_comp_high ({self.target_comp_high})"
            )
        return self


class RecruiterProfile(AgentProfile):
    """Profile for a recruiter agent.

    Represents a recruiter's company assignment, scope of responsibilities,
    and capability level. The recruiter serves as the middleman between
    jobseekers and hiring managers, screening candidates and managing
    communication between both sides.

    Attributes:
        company_id: The company this recruiter works for.
        assigned_posting_ids: Job postings this recruiter is responsible for.
        hiring_manager_ids: Hiring managers this recruiter works with.
        experience_level: General recruiter competence level.
        current_workload: Number of open roles currently being managed.
    """

    company_id: str
    assigned_posting_ids: list[str]
    hiring_manager_ids: list[str]
    experience_level: Literal["junior", "mid", "senior"]
    current_workload: int = Field(ge=0)


class HiringManagerProfile(AgentProfile):
    """Profile for a hiring manager agent.

    Represents a hiring manager's team context, interview style, and
    decision-making tendencies. The hiring manager is the final
    decision-maker on candidates, setting the bar and deciding on offers.

    Attributes:
        company_id: The company this hiring manager belongs to.
        team_size: Current size of the hiring manager's team.
        team_situation: State of the team affecting hiring urgency.
        management_style: How the manager interacts with candidates
            and recruiters.
        technical_bar: Freeform description of what the manager values
            in candidates.
        interview_capacity_per_round: Maximum interviews the manager
            can conduct per round.
        past_hiring_description: Context about previous hires and
            preferences that may reveal implicit biases.
        feedback_clarity: How clearly the manager communicates
            expectations to recruiters.
    """

    company_id: str
    team_size: int = Field(ge=0)
    team_situation: Literal["understaffed", "stable", "growing", "rebuilding"]
    management_style: Literal[
        "detailed_feedback", "vague", "responsive", "slow", "micromanager"
    ]
    technical_bar: str
    interview_capacity_per_round: int = Field(ge=0)
    past_hiring_description: str
    feedback_clarity: Literal["clear", "vague", "contradictory"]

class Education(BaseModel):
    """A single educational credential.

    Attributes:
        school: Name of the institution.
        degree: Degree earned or expected (e.g., BS, MS, PhD).
        year: Graduation year or expected graduation year.
    """

    model_config = ConfigDict(frozen=True)

    school: str
    degree: str
    year: int


class WorkEntry(BaseModel):
    """A single entry in a jobseeker's work history.

    Attributes:
        company: Name of the employer.
        title: Job title held.
        start_year: Year the role began.
        start_month: Month the role began (1-12).
        end_year: Year the role ended, or None if current.
        end_month: Month the role ended (1-12), or None if current.
        bullets: Accomplishment descriptions used for resume building.
    """

    model_config = ConfigDict(frozen=True)

    company: str
    title: str
    # Separate year/month fields instead of date strings to ensure
    # consistent output when seeding with LLMs.
    start_year: int
    start_month: int = Field(ge=1, le=12)
    end_year: int | None = None
    end_month: int | None = Field(default=None, ge=1, le=12)
    bullets: tuple[str, ...]

class AgentState(BaseModel):
    """Mutable state that evolves each round.

    Serialized to JSON for persistence. Stored both as current state on
    the agent and as historical snapshots for the observability timeline.
    """

    round_number: int = 0
    compressed_history: str = ""
    recent_events: list[dict[str, Any]] = []
    current_pipeline: list[dict[str, Any]] = []
    current_resume: str | None = None
    metrics: dict[str, Any] = {}
    last_reflection: str | None = None
