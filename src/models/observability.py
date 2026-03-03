"""Observability models for snapshots, resumes, reflections, events, and config."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ModelParams(BaseModel):
    """LLM parameters for API calls."""

    temperature: float = 0.7
    top_p: float = 0.95
    sonnet_model_version: str = "claude-sonnet-4-20250514"
    haiku_model_version: str = "claude-haiku-4-5-20251001"


class ContextParams(BaseModel):
    """Parameters controlling agent context and history management."""

    compression_frequency: int = 5
    recent_history_window: int = 3
    max_context_tokens: int = 150000


class SimulationStructure(BaseModel):
    """Parameters defining the simulation's turn and round structure."""

    turn_structure: str = "sequential"
    agent_action_order: list[str] = [
        "job_seeker",
        "recruiter",
        "hiring_manager",
    ]
    board_visibility: str = "full"
    reflection_frequency: int = 3
    interview_turn_floor: int = 6
    interview_turn_ceiling: int = 12


class MarketParams(BaseModel):
    """Parameters shaping the simulated job market dynamics."""

    seeker_to_opening_ratio: float = 3.0
    ghost_job_percentage: float = 0.15
    rejection_specificity: str = "low"
    new_postings_per_round: int = 2
    posting_expiry_rounds: int = 10


class ScaleParams(BaseModel):
    """Parameters controlling the simulation's size."""

    num_seekers: int = 10
    num_companies: int = 5
    num_postings: int = 15
    total_rounds: int = 20


class RunConfig(BaseModel):
    """Complete parameter set for a simulation run.

    Stored once at the start of each run. Makes runs reproducible
    and comparable.
    """

    model_params: ModelParams = Field(default_factory=ModelParams)
    context_params: ContextParams = Field(default_factory=ContextParams)
    simulation_structure: SimulationStructure = Field(
        default_factory=SimulationStructure
    )
    market_params: MarketParams = Field(default_factory=MarketParams)
    scale_params: ScaleParams = Field(default_factory=ScaleParams)


class StateSnapshot(BaseModel):
    """Point-in-time capture of an agent's full state.

    Written at the end of every round for every agent. Primary data source
    for tracking behavioral progression over time.
    """

    agent_id: str
    agent_type: str
    round_number: int
    state_json: dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.now)


class ResumeVersion(BaseModel):
    """A single version of a job seeker's resume.

    Append-only — every call to write_resume creates a new row. The trigger
    field records why the rewrite happened.
    """

    id: str
    seeker_id: str
    round_created: int
    full_text: str
    trigger: Literal["initial", "general_rewrite", "tailored", "desperate_overhaul"]
    target_posting_id: str | None = None
    state_summary_at_creation: str


class ReflectionEntry(BaseModel):
    """An agent's periodic self-assessment.

    Captures both the prompt used and the response, plus the active context.
    """

    id: str
    agent_id: str
    agent_type: str
    round_number: int
    prompt_used: str
    response: str
    context_summary: str


class EventEntry(BaseModel):
    """Generic event log for any discrete occurrence.

    Catch-all for everything: application_submitted, rejection_sent,
    interview_scheduled, offer_extended, posting_closed, etc.
    """

    id: str
    agent_id: str | None = None
    round_number: int
    event_type: str
    details: dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.now)
