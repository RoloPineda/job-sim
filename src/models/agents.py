"""Agent profile and state models."""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class AgentProfile(BaseModel):
    """Base profile shared by all agent types.

    Contains the stable identity and disposition that persist throughout
    the simulation. Accumulated experience is stored separately in AgentState.
    """

    id: str
    agent_type: Literal["job_seeker", "recruiter", "hiring_manager"]
    name: str
    disposition: str
    backstory: str


class JobSeekerProfile(AgentProfile):
    """A job seeker's full profile including skills, preferences, and traits."""

    actual_skills: list[str]
    perceived_skills: list[str]
    experience_years: int = Field(ge=0)
    target_role: str
    target_seniority: str
    target_comp_low: int = Field(ge=0)
    target_comp_high: int = Field(ge=0)
    location_flexibility: Literal["rigid", "moderate", "flexible"]
    financial_runway: int = Field(ge=0)
    communication_ability: Literal["strong", "average", "weak"]
    self_awareness: Literal["accurate", "overconfident", "underconfident"]

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
    """A recruiter's profile with company assignment and workload."""

    company_id: str
    hiring_manager_ids: list[str]
    assigned_posting_ids: list[str]
    experience_level: Literal["junior", "mid", "senior"]
    current_workload: int = Field(ge=0)


class HiringManagerProfile(AgentProfile):
    """A hiring manager's profile including team context and interview style."""

    company_id: str
    team_size: int = Field(ge=0)
    team_situation: Literal["understaffed", "stable", "growing", "rebuilding"]
    management_style: Literal[
        "detailed_feedback", "vague", "responsive", "slow", "micromanager"
    ]
    technical_bar: str
    interview_capacity_per_round: int = Field(ge=0)
    past_hiring_description: str


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
