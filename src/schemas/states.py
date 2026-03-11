"""Mutable per-round agent state schemas.

Each agent type has its own state subclass with typed fields. This
replaces the generic metrics dict pattern to prevent key typos and
give IDE support.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class AgentState(BaseModel):
    """Mutable state shared across all agent types.

    Serialized to JSON for persistence. Stored both as current state on
    the agent and as historical snapshots for the observability timeline.
    Role-specific state lives on SeekerState, RecruiterState, or
    HiringManagerState.

    Attributes:
        round_number: Current simulation round.
        compressed_history: Summary of prior rounds for context window
            management.
        recent_events: Events from the last few rounds.
        last_reflection: Most recent self-assessment output.
    """

    round_number: int = 0
    compressed_history: str = ""
    recent_events: list[dict[str, Any]] = []
    last_reflection: str | None = None


class JobSeekerState(AgentState):
    """Mutable per-round state for a jobseeker agent.

    Holds fields that change over the course of a simulation: financial
    position, job preferences that may shift under pressure, the
    current resume version, and application tracking.

    Attributes:
        savings: Dollar savings that deplete over rounds.
        burn_rate: How much the agent spends per round. Round intervals
            can represent different timelines (daily, weekly, monthly)
            as defined in the simulation config.
        target_roles: Role titles the agent is searching for.
        target_seniority: Desired seniority level.
        target_comp_low: Minimum acceptable compensation in dollars.
        target_comp_high: Ideal compensation target in dollars.
        location_flexibility: Willingness to relocate.
        remote_preference: Preference for remote, hybrid, or onsite work.
        current_resume: The active resume text, or None if not yet written.
        current_pipeline: Active applications being tracked.
        total_applications: Cumulative applications submitted.
        total_rejections: Cumulative rejections received.
    """

    savings: int = Field(ge=0)
    burn_rate: int = Field(gt=0)
    target_roles: list[str] = Field(min_length=1)
    target_seniority: Literal["junior", "mid", "senior", "lead", "staff"]
    target_comp_low: int = Field(ge=0)
    target_comp_high: int = Field(ge=0)
    location_flexibility: Literal["rigid", "moderate", "flexible"]
    remote_preference: Literal[
        "remote_only", "hybrid", "onsite", "no_preference"
    ]
    current_resume: str | None = None
    current_pipeline: list[dict[str, Any]] = []
    total_applications: int = 0
    total_rejections: int = 0

    @model_validator(mode="after")
    def validate_comp_range(self) -> "SeekerState":
        """Ensure target_comp_low does not exceed target_comp_high."""
        if self.target_comp_low > self.target_comp_high:
            raise ValueError(
                f"target_comp_low ({self.target_comp_low}) must not exceed "
                f"target_comp_high ({self.target_comp_high})"
            )
        return self


class RecruiterState(AgentState):
    """Mutable per-round state for a recruiter agent.

    Tracks the recruiter's active pipeline and screening metrics with
    typed fields instead of a generic metrics dict.

    Attributes:
        current_pipeline: Active candidate entries being managed.
        total_screened: Cumulative applications reviewed.
        total_forwarded: Cumulative candidates sent to hiring managers.
        total_rejected: Cumulative candidates rejected.
    """

    current_pipeline: list[dict[str, Any]] = []
    total_screened: int = 0
    total_forwarded: int = 0
    total_rejected: int = 0


class HiringManagerState(AgentState):
    """Mutable per-round state for a hiring manager agent.

    Tracks interview activity and decision counts.

    Attributes:
        interviews_conducted: Cumulative interviews completed.
        candidates_advanced: Cumulative candidates moved forward.
        candidates_rejected: Cumulative candidates passed on.
    """

    interviews_conducted: int = 0
    candidates_advanced: int = 0
    candidates_rejected: int = 0