"""Simulation run configuration for the Candor simulation.

Stored once at the start of each run to make runs reproducible and
comparable. For now this config assumes Claude only. Might extend to
other models later.
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
        market_condition: Whether the market favors employers,
            employees, or is balanced. Fed into recruiter and HM
            prompts to shape behavior.
        ghost_job_percentage: Percentage of postings seeded as ghost
            jobs that never advance candidates.
        new_postings_per_round: How many new jobs appear on the board
            each round.
        posting_expiry_rounds: How many rounds a posting stays active
            before expiring.
        num_seekers: Total number of jobseeker agents.
        num_companies: Total number of companies.
        num_postings: Total number of initial job postings seeded at
            the start.
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
    turn_structure: str # might
    agent_action_order: list[str]
    reflection_frequency: int = Field(gt=0)
    interview_turn_floor: int = Field(gt=0)
    interview_turn_ceiling: int = Field(gt=0)

    # Market parameters
    market_condition: Literal["employer_favored", "balanced", "employee_favored"]
    ghost_job_percentage: float = Field(ge=0.0, le=1.0)
    new_postings_per_round: int = Field(ge=0)
    posting_expiry_rounds: int = Field(gt=0)

    # Scale parameters
    num_seekers: int = Field(gt=0)
    num_companies: int = Field(gt=0)
    num_postings: int = Field(gt=0)
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