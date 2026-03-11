"""Single-turn validation script for the jobseeker agent.

Runs one turn of Sarah Chen's job search against the real Anthropic API.
Logs everything: prompts sent, model responses, tool inputs/outputs,
cost, resumes written, applications submitted, and final state.
No database writes.

Usage:
    uv run python scripts/single_turn_test.py
"""

import asyncio
import logging
import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv

load_dotenv()

from anthropic import AsyncAnthropic
from anthropic.types import Message, TextBlock, ToolUseBlock

from agents.job_seeker import JobSeekerAgent
from schemas.company import JobPosting
from schemas.config import RunConfig
from schemas.profiles import JobSeekerProfile
from schemas.shared import Education, WorkEntry
from schemas.states import JobSeekerState

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
LOG_FILE = os.path.join(LOG_DIR, "single_turn_test.log")


def _configure_logging() -> logging.Logger:
    """Sets up file and console logging.

    Returns:
        The configured logger instance.
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("single_turn_test")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    file_handler = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(message)s"))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


log = _configure_logging()


def _log_header(call_number: int) -> None:
    log.debug("\n%s", "=" * 60)
    log.debug("API CALL #%d", call_number)
    log.debug("=" * 60)


def _log_user_message(messages: list[dict[str, Any]]) -> None:
    last_msg = messages[-1]
    log.debug("\n--- USER MESSAGE (last of %d) ---", len(messages))
    if isinstance(last_msg["content"], str):
        log.debug("%s", last_msg["content"])
        return
    for block in last_msg["content"]:
        if block.get("type") == "tool_result":
            err = " [ERROR]" if block.get("is_error") else ""
            log.debug("  [tool_result for %s]%s", block["tool_use_id"], err)
            log.debug("    %s", block.get("content", ""))
        else:
            log.debug("  %s", block)


def _log_response(response: Message) -> None:
    log.debug("\n--- MODEL RESPONSE ---")
    log.debug("  Stop reason: %s", response.stop_reason)
    for block in response.content:
        if isinstance(block, TextBlock):
            log.debug("  [text] %s", block.text)
        elif isinstance(block, ToolUseBlock):
            log.debug("  [tool_use] %s (id=%s)", block.name, block.id)
            log.debug("    input: %s", block.input)


class InstrumentedJobSeeker(JobSeekerAgent):
    """Wraps JobSeekerAgent to log prompts, responses, and tool I/O."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._call_number = 0

    async def call_api(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> Message:
        self._call_number += 1
        _log_header(self._call_number)
        if self._call_number == 1:
            log.debug("\n--- SYSTEM PROMPT ---\n%s", system)
        _log_user_message(messages)

        response = await super().call_api(system, messages, tools, model)
        _log_response(response)
        return response

    async def handle_tool_call(
        self, tool_name: str, tool_input: dict[str, Any]
    ) -> str:
        result = await super().handle_tool_call(tool_name, tool_input)
        log.debug("\n--- TOOL RESULT: %s ---", tool_name)
        log.debug("  %s", result)
        return result


def build_sarah() -> JobSeekerProfile:
    """Builds Sarah Chen's immutable profile."""
    return JobSeekerProfile(
        id="js-sarah",
        agent_type="job_seeker",
        name="Sarah Chen",
        disposition=(
            "Underconfident and methodical. Second-guesses herself even "
            "when she knows the answer. Tends to over-prepare and "
            "under-promote."
        ),
        backstory=(
            "You spent four years at a mid-size fintech company building "
            "data pipelines and ML models. You were well-regarded by your "
            "team but never pushed for promotion. When the company went "
            "through layoffs six months ago, you were cut despite strong "
            "performance reviews. You suspect it was political but you "
            "blame yourself for not being more visible. This is your first "
            "real job search since college and you have no idea what you're "
            "worth on the open market."
        ),
        location="Austin, TX",
        education_history=[
            Education(school="UT Austin", degree="BS Computer Science", year=2019),
        ],
        actual_skills=[
            "Python",
            "SQL",
            "Spark",
            "Airflow",
            "scikit-learn",
            "PyTorch",
            "data modeling",
            "A/B testing",
        ],
        perceived_skills=["Python", "SQL", "Airflow", "some ML"],
        work_history=[
            WorkEntry(
                company="Greenline Financial",
                title="Data Engineer II",
                start_year=2021,
                start_month=3,
                end_year=2024,
                end_month=6,
                bullets=(
                    "Built and maintained ETL pipelines processing 2M+ transactions daily",
                    "Developed fraud detection model that reduced false positives by 30%",
                    "Led migration from Hadoop to Spark on AWS EMR",
                ),
            ),
            WorkEntry(
                company="Greenline Financial",
                title="Junior Data Engineer",
                start_year=2019,
                start_month=7,
                end_year=2021,
                end_month=3,
                bullets=(
                    "Wrote SQL and dbt models for the analytics warehouse",
                    "Built and scheduled Airflow DAGs for daily data loads",
                ),
            ),
        ],
        experience_years=5,
        self_awareness="underconfident",
        communication_ability="average",
    )


def build_sarah_state() -> JobSeekerState:
    """Builds Sarah Chen's initial mutable state."""
    return JobSeekerState(
        round_number=1,
        target_roles=["Data Engineer", "ML Engineer"],
        target_seniority="mid",
        target_comp_low=130_000,
        target_comp_high=165_000,
        location_flexibility="moderate",
        remote_preference="remote_only",
        savings=28_000,
        burn_rate=4_200,
    )


def build_postings() -> list[JobPosting]:
    """Builds the set of visible job postings for the test."""
    return [
        JobPosting(
            id="post_014",
            company_id="comp-meridian",
            company_name="Meridian Health Systems",
            hiring_manager_id="hm-meridian-1",
            title="Data Engineer",
            department="Data Platform",
            description=(
                "Join our data platform team to build and scale the "
                "pipelines powering clinical analytics. You'll work with "
                "large healthcare datasets and help shape our data "
                "architecture as we grow."
            ),
            requirements=[
                "3+ years building data pipelines",
                "Python and SQL proficiency",
                "Experience with Spark or similar",
                "Familiarity with cloud platforms (AWS preferred)",
            ],
            salary_range_low=135_000,
            salary_range_high=160_000,
            location="Austin, TX",
            remote=True,
            seniority="mid",
            round_posted=1,
        ),
        JobPosting(
            id="post_027",
            company_id="comp-lattice",
            company_name="Lattice AI",
            hiring_manager_id="hm-lattice-1",
            title="ML Engineer",
            department="Applied ML",
            description=(
                "We're looking for an ML engineer to build and deploy "
                "production models for our recommendation platform. You'll "
                "own the full lifecycle from training to serving."
            ),
            requirements=[
                "3+ years in production ML systems",
                "Strong Python, PyTorch or TensorFlow",
                "Experience with feature stores and model serving",
                "Familiarity with experiment tracking",
            ],
            salary_range_low=155_000,
            salary_range_high=190_000,
            location="San Francisco, CA",
            remote=True,
            seniority="mid",
            round_posted=1,
        ),
        JobPosting(
            id="post_033",
            company_id="comp-bowman",
            company_name="Bowman & Associates",
            hiring_manager_id="hm-bowman-1",
            title="Senior Data Engineer",
            department="Engineering",
            description=(
                "Lead data engineering initiatives for our consulting "
                "clients. You'll design data warehouses, build pipelines, "
                "and mentor junior engineers."
            ),
            requirements=[
                "7+ years data engineering",
                "Expert-level SQL and Python",
                "Experience leading technical projects",
                "Strong data warehousing knowledge",
            ],
            location="Dallas, TX",
            remote=False,
            seniority="senior",
            round_posted=1,
        ),
        JobPosting(
            id="post_041",
            company_id="comp-presto",
            company_name="Presto Commerce",
            hiring_manager_id="hm-presto-1",
            title="Data Engineer II",
            department="Data",
            description=(
                "Help us build the data infrastructure behind a fast-growing "
                "e-commerce platform. You'll work on event pipelines, "
                "warehouse modeling, and reporting systems."
            ),
            requirements=[
                "2-4 years data engineering",
                "Python, SQL, Airflow",
                "AWS data services",
                "E-commerce domain preferred",
            ],
            salary_range_low=120_000,
            salary_range_high=140_000,
            location="Austin, TX",
            remote=False,
            seniority="mid",
            round_posted=1,
        ),
        JobPosting(
            id="post_058",
            company_id="comp-novabridge",
            company_name="NovaBridge Technologies",
            hiring_manager_id="hm-novabridge-1",
            title="Data & ML Engineer",
            department="Platform",
            description=(
                "We need someone who can bridge data engineering and ML. "
                "You'll build end-to-end pipelines from raw data ingestion "
                "through model deployment and monitoring."
            ),
            requirements=[
                "3-5 years in data engineering or ML engineering",
                "Python, SQL, and at least one ML framework",
                "End-to-end pipelines from ingestion to model deployment",
                "Strong communicator in async environments",
            ],
            location="Remote",
            remote=True,
            seniority="mid",
            round_posted=1,
            is_ghost=True,
        ),
    ]


def build_config() -> RunConfig:
    """Builds simulation-wide configuration for the test."""
    return RunConfig(
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


async def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("Set ANTHROPIC_API_KEY in .env or environment.")
        sys.exit(1)

    client = AsyncAnthropic(api_key=api_key)
    profile = build_sarah()
    config = build_config()
    state = build_sarah_state()
    postings = build_postings()

    agent = InstrumentedJobSeeker(
        profile=profile,
        config=config,
        state=state,
        postings=postings,
        client=client,
    )

    log.info("=" * 60)
    log.info("SINGLE-TURN VALIDATION: Sarah Chen, Round 1")
    log.info("=" * 60)

    t0 = time.monotonic()
    result = await agent.run_turn(round_number=1)
    elapsed = time.monotonic() - t0

    log.info("")
    log.info("=" * 60)
    log.info("TURN RESULT")
    log.info("=" * 60)
    log.info("  Tool calls:      %d", result.tool_calls_made)
    log.info("  API calls:       %d", result.api_calls_made)
    log.info("  Input tokens:    %s", f"{result.total_input_tokens:,}")
    log.info("  Output tokens:   %s", f"{result.total_output_tokens:,}")
    log.info("  Estimated cost:  $%.4f", result.total_cost)
    log.info("  Soft cap hit:    %s", result.soft_cap_hit)
    log.info("  Skipped:         %s", result.skipped)
    if result.skip_reason:
        log.info("  Skip reason:     %s", result.skip_reason)
    log.info("  Wall time:       %.1fs", elapsed)

    log.info("")
    log.info("-" * 60)
    log.info("RESUMES WRITTEN (%d)", len(agent.resume_versions))
    log.info("-" * 60)
    for rv in agent.resume_versions:
        log.info("  ID:      %s", rv.id)
        log.info("  Trigger: %s", rv.trigger)
        log.info("  Target:  %s", rv.target_posting_id or "general")
        log.info("  State:   %s", rv.state_summary_at_creation)
        log.info("  Text:\n%s", rv.full_text)
        log.info("")

    log.info("-" * 60)
    log.info("APPLICATIONS SUBMITTED (%d)", len(agent.applications))
    log.info("-" * 60)
    for app in agent.applications:
        log.info("  ID:          %s", app.id)
        log.info("  Posting:     %s", app.posting_id)
        log.info("  Resume ver:  %s", app.resume_version_id)
        log.info("")

    log.info("-" * 60)
    log.info("FINAL STATE")
    log.info("-" * 60)
    log.info("  Has resume:          %s", state.current_resume is not None)
    log.info("  Pipeline count:      %d", len(state.current_pipeline))
    log.info("  Total applications:  %d", state.total_applications)
    log.info("  Total rejections:    %d", state.total_rejections)
    log.info("")
    log.info("Full log written to %s", LOG_FILE)


if __name__ == "__main__":
    asyncio.run(main())