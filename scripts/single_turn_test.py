"""Single-turn validation script for the jobseeker agent.

Runs one turn of Sarah Chen's job search against the real Anthropic API.
Prints everything: prompts sent, model responses, tool inputs/outputs,
cost, resumes written, applications submitted, and final state.
No database writes.

Usage:
    uv run python scripts/single_turn_test.py
"""

import asyncio
import os
import sys
import time
from typing import Any

# src/ is the package root for internal imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv

load_dotenv()

from anthropic import AsyncAnthropic
from anthropic.types import Message, TextBlock, ToolUseBlock

from agents.job_seeker import JobSeekerAgent
from schemas.agents import AgentState, Education, JobSeekerProfile, WorkEntry
from schemas.company import JobPosting
from schemas.config import RunConfig


def _print_header(call_number: int) -> None:
    print(f"\n{'='*60}")
    print(f"API CALL #{call_number}")
    print(f"{'='*60}")


def _print_user_message(messages: list[dict[str, Any]]) -> None:
    last_msg = messages[-1]
    print(f"\n--- USER MESSAGE (last of {len(messages)}) ---")
    if isinstance(last_msg["content"], str):
        print(last_msg["content"])
        return
    for block in last_msg["content"]:
        if block.get("type") == "tool_result":
            err = " [ERROR]" if block.get("is_error") else ""
            print(f"  [tool_result for {block['tool_use_id']}]{err}")
            print(f"    {block.get('content', '')}")
        else:
            print(f"  {block}")


def _print_response(response: Message) -> None:
    print("\n--- MODEL RESPONSE ---")
    print(f"  Stop reason: {response.stop_reason}")
    for block in response.content:
        if isinstance(block, TextBlock):
            print(f"  [text] {block.text}")
        elif isinstance(block, ToolUseBlock):
            print(f"  [tool_use] {block.name} (id={block.id})")
            print(f"    input: {block.input}")

class InstrumentedJobSeeker(JobSeekerAgent):
    """Wraps JobSeekerAgent to print prompts, responses, and tool I/O."""

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
        _print_header(self._call_number)
        if self._call_number == 1:
            print(f"\n--- SYSTEM PROMPT ---\n{system}")
        _print_user_message(messages)

        response = await super().call_api(system, messages, tools, model)
        _print_response(response)
        return response

    async def handle_tool_call(
        self, tool_name: str, tool_input: dict[str, Any]
    ) -> str:
        result = await super().handle_tool_call(tool_name, tool_input)
        print(f"\n--- TOOL RESULT: {tool_name} ---")
        print(f"  {result}")
        return result

def build_sarah() -> JobSeekerProfile:
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
            "Python", "SQL", "Spark", "Airflow", "scikit-learn",
            "PyTorch", "data modeling", "A/B testing",
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
        print("ERROR: Set ANTHROPIC_API_KEY in .env or environment.")
        sys.exit(1)

    client = AsyncAnthropic(api_key=api_key)
    profile = build_sarah()
    config = build_config()
    state = AgentState(round_number=1)
    postings = build_postings()
    recruiter_map = {
        "post_014": "rec-001",
        "post_027": "rec-002",
    }

    agent = InstrumentedJobSeeker(
        profile=profile,
        config=config,
        state=state,
        postings=postings,
        recruiter_map=recruiter_map,
        client=client,
    )

    print("=" * 60)
    print("SINGLE-TURN VALIDATION: Sarah Chen, Round 1")
    print("=" * 60)

    t0 = time.monotonic()
    result = await agent.run_turn(round_number=1)
    elapsed = time.monotonic() - t0

    # Turn summary
    print()
    print("=" * 60)
    print("TURN RESULT")
    print("=" * 60)
    print(f"  Tool calls:      {result.tool_calls_made}")
    print(f"  API calls:       {result.api_calls_made}")
    print(f"  Input tokens:    {result.total_input_tokens:,}")
    print(f"  Output tokens:   {result.total_output_tokens:,}")
    print(f"  Estimated cost:  ${result.total_cost:.4f}")
    print(f"  Soft cap hit:    {result.soft_cap_hit}")
    print(f"  Skipped:         {result.skipped}")
    if result.skip_reason:
        print(f"  Skip reason:     {result.skip_reason}")
    print(f"  Wall time:       {elapsed:.1f}s")

    # Resumes
    print()
    print("-" * 60)
    print(f"RESUMES WRITTEN ({len(agent.resume_versions)})")
    print("-" * 60)
    for rv in agent.resume_versions:
        print(f"  ID:      {rv.id}")
        print(f"  Trigger: {rv.trigger}")
        print(f"  Target:  {rv.target_posting_id or 'general'}")
        print(f"  State:   {rv.state_summary_at_creation}")
        print(f"  Text:\n{rv.full_text}")
        print()

    # Applications
    print("-" * 60)
    print(f"APPLICATIONS SUBMITTED ({len(agent.applications)})")
    print("-" * 60)
    for app in agent.applications:
        print(f"  ID:          {app.id}")
        print(f"  Posting:     {app.posting_id}")
        print(f"  Recruiter:   {app.recruiter_id or 'none (background)'}")
        print(f"  Resume ver:  {app.resume_version_id}")
        print()

    # Final state
    print("-" * 60)
    print("FINAL STATE")
    print("-" * 60)
    print(f"  Has resume:          {state.current_resume is not None}")
    print(f"  Pipeline count:      {len(state.current_pipeline)}")
    print(f"  Total applications:  {state.metrics.get('total_applications', 0)}")
    print()


if __name__ == "__main__":
    asyncio.run(main())