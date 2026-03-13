"""Simulation run configuration for the Candor simulation.

Stored once at the start of each run to make runs reproducible and
comparable. For now this config assumes Claude only. Might extend to
other schemas later.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RunConfig(BaseModel):
    """Complete parameter set for a simulation run.

    Groups configuration into five categories: model parameters that
    control LLM behavior, context parameters that manage prompt size
    and history, simulation structure parameters that define round
    organization, market parameters that shape the job market, and
    scale parameters that control simulation size.

    Attributes:
        temperature: Controls agent behavior variance. Higher values
            produce more creative and unpredictable decisions.
        top_p: Controls output diversity alongside temperature.
            Generally leave close to 1.0.
        sonnet_model_version: Model for main agent decisions like
            applying, interviewing, negotiating, and reflecting.
        haiku_model_version: Model for cheaper operations like history
            compression and summarization.
        compression_frequency: How often (in rounds) older events get
            compressed into a summary.
        recent_history_window: How many rounds of raw uncompressed
            events the agent sees in its prompt.
        max_context_tokens: Hard ceiling on total tokens in an agent's
            prompt.
        turn_structure: How a single round is organized.
        agent_action_order: Order in which agents take their turns
            each round.
        reflection_frequency: How often (in rounds) agents run a
            self-reflection prompt.
        interview_turn_floor: Minimum turns in an interview
            conversation.
        interview_turn_ceiling: Maximum turns in an interview
            conversation.
        tool_call_soft_cap: Maximum tool calls per agent per round
            before the engine injects a wrap-up nudge. The agent can
            still make one more call after the cap is hit.
        market_condition: Whether the market favors employers,
            employees, or is balanced. Fed into recruiter and HM
            prompts to shape behavior.
        ghost_job_percentage: Percentage of postings seeded as ghost
            jobs that never advance candidates.
        posting_expiry_rounds: How many rounds a posting stays active
            before expiring.
        min_postings_per_role_type: Minimum open postings per role
            type on the board. When a role type drops below this
            threshold, new background companies are generated.
        num_seekers: Total number of jobseeker agents.
        num_agent_companies: Number of companies backed by recruiter
            and hiring manager agents.
        num_background_companies: Number of deterministic background
            companies that respond based on parameters alone.
        postings_per_agent_company: Number of initial job postings
            seeded per agent-backed company.
        postings_per_background_company_range: Tuple of (min, max)
            postings seeded per background company.
        total_rounds: How many rounds the simulation runs.
    """

    model_config = ConfigDict(frozen=True)

    # Model parameters
    temperature: float = Field(ge=0.0, le=2.0)
    top_p: float = Field(ge=0.0, le=1.0, default=1.0)
    sonnet_model_version: str
    haiku_model_version: str

    # Context parameters
    compression_frequency: int = Field(gt=0)
    recent_history_window: int = Field(gt=0)
    max_context_tokens: int = Field(gt=0)

    # Simulation structure parameters
    turn_structure: str
    agent_action_order: list[str]
    reflection_frequency: int = Field(gt=0)
    interview_turn_floor: int = Field(gt=0)
    interview_turn_ceiling: int = Field(gt=0)
    tool_call_soft_cap: int = Field(gt=0)

    # Market parameters
    market_condition: Literal["employer_favored", "balanced", "employee_favored"]
    ghost_job_percentage: float = Field(ge=0.0, le=1.0)
    posting_expiry_rounds: int = Field(gt=0)
    min_postings_per_role_type: int = Field(gt=0)

    # Scale parameters
    num_seekers: int = Field(gt=0)
    num_agent_companies: int = Field(gt=0)
    num_background_companies: int = Field(gt=0)
    postings_per_agent_company: int = Field(gt=0)
    postings_per_background_company_range: tuple[int, int]
    total_rounds: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_interview_turns(self) -> "RunConfig":
        """Ensure interview_turn_floor does not exceed interview_turn_ceiling."""
        if self.interview_turn_floor > self.interview_turn_ceiling:
            raise ValueError(
                f"interview_turn_floor ({self.interview_turn_floor}) must not "
                f"exceed interview_turn_ceiling ({self.interview_turn_ceiling})"
            )
        return self

    @model_validator(mode="after")
    def validate_background_posting_range(self) -> "RunConfig":
        """Ensure the background company posting range is valid."""
        low, high = self.postings_per_background_company_range
        if low < 1:
            raise ValueError(
                f"postings_per_background_company_range lower bound ({low}) must be at least 1"
            )
        if low > high:
            raise ValueError(
                f"postings_per_background_company_range lower bound "
                f"({low}) must not exceed upper bound ({high})"
            )
        return self
