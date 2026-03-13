"""Shared test factory functions for building valid schema instances."""

from typing import Any

from anthropic.types import Message, TextBlock, ToolUseBlock, Usage

from schemas.company import CompanyProfile, JobPosting
from schemas.config import RunConfig
from schemas.profiles import (
    AgentProfile,
    HiringManagerProfile,
    JobSeekerProfile,
    RecruiterProfile,
)
from schemas.shared import Education, WorkEntry
from schemas.states import JobSeekerState


def make_config(**overrides) -> RunConfig:
    """Build a valid RunConfig, merging any field overrides.

    Args:
        **overrides: Any RunConfig fields to override.

    Returns:
        A fully constructed RunConfig.
    """
    defaults = dict(
        temperature=0.7,
        top_p=1.0,
        sonnet_model_version="claude-sonnet-4-20250514",
        haiku_model_version="claude-haiku-4-20250414",
        compression_frequency=5,
        recent_history_window=3,
        max_context_tokens=4096,
        turn_structure="sequential",
        agent_action_order=["job_seeker", "recruiter", "hiring_manager"],
        reflection_frequency=3,
        interview_turn_floor=2,
        interview_turn_ceiling=6,
        tool_call_soft_cap=6,
        market_condition="balanced",
        ghost_job_percentage=0.1,
        posting_expiry_rounds=10,
        min_postings_per_role_type=3,
        num_seekers=20,
        num_agent_companies=3,
        num_background_companies=10,
        postings_per_agent_company=2,
        postings_per_background_company_range=(1, 3),
        total_rounds=30,
    )
    defaults.update(overrides)
    return RunConfig(**defaults)


def make_education(**overrides) -> Education:
    """Build a minimal Education instance.

    Args:
        **overrides: Any Education fields to override.

    Returns:
        A fully constructed Education.
    """
    defaults = dict(school="State University", degree="BS", year=2020)
    defaults.update(overrides)
    return Education(**defaults)


def make_work_entry(**overrides) -> WorkEntry:
    """Build a minimal WorkEntry instance.

    Args:
        **overrides: Any WorkEntry fields to override.

    Returns:
        A fully constructed WorkEntry.
    """
    defaults = dict(
        company="Acme Corp",
        title="Engineer",
        start_year=2020,
        start_month=6,
        end_year=2022,
        end_month=5,
        bullets=("Built things.",),
    )
    defaults.update(overrides)
    return WorkEntry(**defaults)


def make_job_seeker(
    education: Education | None = None,
    work_entry: WorkEntry | None = None,
    **overrides,
) -> JobSeekerProfile:
    """Build a valid JobSeekerProfile, merging any field overrides.

    Args:
        education: An Education instance. Defaults to make_education().
        work_entry: A WorkEntry instance. Defaults to make_work_entry().
        **overrides: Any JobSeekerProfile fields to override.

    Returns:
        A fully constructed JobSeekerProfile.
    """
    if education is None:
        education = make_education()
    if work_entry is None:
        work_entry = make_work_entry()

    defaults = dict(
        id="js-1",
        agent_type="job_seeker",
        name="Alice",
        disposition="motivated",
        backstory="Grew up tinkering with computers.",
        location="Austin, TX",
        education_history=[education],
        actual_skills=["python", "sql"],
        perceived_skills=["python", "sql", "leadership"],
        work_history=[work_entry],
        experience_years=3,
        self_awareness="accurate",
        communication_ability="strong",
    )
    defaults.update(overrides)
    return JobSeekerProfile(**defaults)


def make_seeker_profile(**overrides) -> AgentProfile:
    """Build a minimal jobseeker AgentProfile.

    Uses the base AgentProfile rather than the full JobSeekerProfile.
    Useful when only the identity fields are needed.

    Args:
        **overrides: Any AgentProfile fields to override.

    Returns:
        A fully constructed AgentProfile with job_seeker type.
    """
    defaults = dict(
        id="js-1",
        agent_type="job_seeker",
        name="Sarah Chen",
        disposition="Methodical and slightly risk-averse.",
        backstory=(
            "Spent 5 years at a mid-size fintech company before being "
            "laid off during a restructuring. Still processing the shock."
        ),
        location="Austin, TX",
    )
    defaults.update(overrides)
    return AgentProfile(**defaults)


def make_seeker_state(**overrides) -> JobSeekerState:
    """Build a valid JobSeekerState, merging any field overrides.

    Args:
        **overrides: Any JobSeekerState fields to override.

    Returns:
        A fully constructed JobSeekerState.
    """
    defaults = dict(
        round_number=1,
        savings=10_000,
        burn_rate=2_000,
        target_roles=["Software Engineer"],
        target_seniority="mid",
        target_comp_low=80_000,
        target_comp_high=120_000,
        location_flexibility="moderate",
        remote_preference="hybrid",
    )
    defaults.update(overrides)
    return JobSeekerState(**defaults)


def make_recruiter_profile(**overrides) -> RecruiterProfile:
    """Build a minimal RecruiterProfile.

    Args:
        **overrides: Any RecruiterProfile fields to override.

    Returns:
        A fully constructed RecruiterProfile.
    """
    defaults = dict(
        id="rec-1",
        agent_type="recruiter",
        name="James Park",
        disposition="Empathetic but overworked.",
        backstory="Three years of agency recruiting before going in-house.",
        location="San Francisco, CA",
        company_id="comp-1",
        assigned_posting_ids=["post-1"],
        hiring_manager_ids=["hm-1"],
        experience_level="mid",
        current_workload=4,
    )
    defaults.update(overrides)
    return RecruiterProfile(**defaults)


def make_hm_profile(**overrides) -> HiringManagerProfile:
    """Build a minimal HiringManagerProfile.

    Args:
        **overrides: Any HiringManagerProfile fields to override.

    Returns:
        A fully constructed HiringManagerProfile.
    """
    defaults = dict(
        id="hm-1",
        agent_type="hiring_manager",
        name="Dana Reeves",
        disposition="Direct and impatient.",
        backstory="Built the backend team from scratch over two years.",
        location="New York, NY",
        company_id="comp-1",
        team_size=6,
        team_situation="understaffed",
        management_style="detailed_feedback",
        technical_bar="Strong systems design, can own a service end-to-end.",
        interview_capacity_per_round=3,
        past_hiring_description="Hired mostly senior engineers from FAANG.",
        feedback_clarity="clear",
    )
    defaults.update(overrides)
    return HiringManagerProfile(**defaults)


def make_company(**overrides) -> CompanyProfile:
    """Build a valid CompanyProfile, merging any field overrides.

    Args:
        **overrides: Any CompanyProfile fields to override.

    Returns:
        A fully constructed CompanyProfile.
    """
    defaults = dict(
        id="co-1",
        name="Acme Inc",
        industry="technology",
        size="mid",
        growth_stage="scaling",
        culture_description="Fast-paced and collaborative.",
        budget_flexibility="moderate",
        responsiveness_pattern="fast",
        base_response_delay=3,
        response_delay_variance=1,
        rejection_specificity="moderate",
    )
    defaults.update(overrides)
    return CompanyProfile(**defaults)


def make_job_posting(**overrides) -> JobPosting:
    """Build a valid JobPosting, merging any field overrides.

    Args:
        **overrides: Any JobPosting fields to override.

    Returns:
        A fully constructed JobPosting.
    """
    defaults = dict(
        id="post-1",
        company_id="co-1",
        company_name="Acme Inc",
        hiring_manager_id="hm-1",
        title="Software Engineer",
        department="Engineering",
        description="Build and maintain backend services.",
        requirements=["Python", "SQL", "3+ years experience"],
        salary_range_low=90_000,
        salary_range_high=140_000,
        location="Austin, TX",
        remote=True,
        seniority="mid",
        round_posted=0,
    )
    defaults.update(overrides)
    return JobPosting(**defaults)


def make_sample_tools() -> list[dict[str, Any]]:
    """Build a list of sample tool definitions in Anthropic API format.

    Returns:
        Two tool definitions: browse_job_board and submit_application.
    """
    return [
        {
            "name": "browse_job_board",
            "description": "View current open postings.",
            "input_schema": {
                "type": "object",
                "properties": {"filter_role": {"type": "string"}},
            },
        },
        {
            "name": "submit_application",
            "description": "Apply to a posting.",
            "input_schema": {
                "type": "object",
                "properties": {"posting_id": {"type": "string"}},
                "required": ["posting_id"],
            },
        },
    ]


# Mock API response factories


def make_usage(input_tokens: int = 100, output_tokens: int = 50) -> Usage:
    """Build a Usage object with sensible defaults for testing."""
    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )


def make_text_response(text: str = "I'll think about it.") -> Message:
    """Build a Message with a single text block (no tool use)."""
    return Message(
        id="msg_test",
        content=[TextBlock(type="text", text=text)],
        model="claude-sonnet-4-20250514",
        role="assistant",
        stop_reason="end_turn",
        type="message",
        usage=make_usage(),
    )


def make_tool_response(
    tool_name: str = "browse_job_board",
    tool_input: dict | None = None,
    tool_id: str = "toolu_test",
    text: str | None = None,
) -> Message:
    """Build a Message containing a single tool_use block.

    Args:
        tool_name: Name of the tool being called.
        tool_input: Input dict for the tool call.
        tool_id: Unique tool use ID.
        text: Optional preceding text block.
    """
    content = []
    if text:
        content.append(TextBlock(type="text", text=text))
    content.append(
        ToolUseBlock(
            type="tool_use",
            id=tool_id,
            name=tool_name,
            input=tool_input or {},
        )
    )
    return Message(
        id="msg_test",
        content=content,
        model="claude-sonnet-4-20250514",
        role="assistant",
        stop_reason="tool_use",
        type="message",
        usage=make_usage(),
    )


def make_multi_tool_response(
    tools: list[tuple[str, dict, str]],
) -> Message:
    """Build a Message with multiple tool_use blocks.

    Args:
        tools: List of (name, input, id) tuples.
    """
    content = [
        ToolUseBlock(type="tool_use", id=tid, name=name, input=inp) for name, inp, tid in tools
    ]
    return Message(
        id="msg_test",
        content=content,
        model="claude-sonnet-4-20250514",
        role="assistant",
        stop_reason="tool_use",
        type="message",
        usage=make_usage(),
    )
