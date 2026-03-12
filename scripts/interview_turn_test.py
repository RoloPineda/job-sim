"""Interview path validation script.

Runs a multi-turn interview between Sarah Chen (job seeker) and
Dana Reeves (hiring manager) against the real Anthropic API. Builds
the transcript incrementally, alternating speakers, and logs every
payload and response.

Validates that the prompt builder correctly maps speakers to API
roles, merges consecutive messages, and produces valid alternating
user/assistant payloads at each turn.

No database writes. No agent framework dependencies beyond the
prompt builder and schemas.

Usage:
    uv run python scripts/interview_turn_test.py
"""

import asyncio
import logging
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv

load_dotenv()

from anthropic import AsyncAnthropic
from anthropic.types import Message, TextBlock

from engine.prompt_builder import PromptBuilder
from schemas.config import RunConfig
from schemas.profiles import HiringManagerProfile, JobSeekerProfile
from schemas.shared import Education, WorkEntry

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
LOG_FILE = os.path.join(LOG_DIR, "interview_turn_test.log")


def _configure_logging() -> logging.Logger:
    """Sets up file and console logging.

    Returns:
        The configured logger instance.
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("interview_turn_test")
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


def build_sarah() -> JobSeekerProfile:
    """Builds Sarah Chen's immutable profile for the interview."""
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
    )


def build_dana() -> HiringManagerProfile:
    """Builds Dana Reeves's immutable profile for the interview."""
    return HiringManagerProfile(
        id="hm-meridian-1",
        agent_type="hiring_manager",
        name="Dana Reeves",
        disposition=(
            "Direct and no-nonsense. Values clarity and ownership. "
            "Respects people who can explain their thinking, even "
            "when the answer is 'I don't know.' Loses patience with "
            "vague or evasive responses."
        ),
        backstory=(
            "You've managed the Data Platform team at Meridian Health "
            "Systems for three years. Your team builds the pipelines "
            "that power clinical analytics across 40+ hospitals. You "
            "lost two senior engineers last quarter and you need someone "
            "who can hit the ground running. You're skeptical of "
            "candidates who over-promise and under-deliver."
        ),
        location="Austin, TX",
        company_id="comp-meridian",
        team_size=6,
        team_situation="understaffed",
        management_style="detailed_feedback",
        technical_bar=(
            "Strong fundamentals in Python and SQL. Hands-on pipeline "
            "experience at scale. Can explain tradeoffs in their own "
            "architecture decisions. Bonus if they've worked with "
            "healthcare or regulated data."
        ),
        interview_capacity_per_round=2,
        past_hiring_description=(
            "Last two hires were senior engineers who interviewed well "
            "but struggled with ambiguity. Dana now weights ownership "
            "and independent problem-solving more heavily than raw "
            "technical depth."
        ),
        feedback_clarity="clear",
    )


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


ROLE_CONTEXT = (
    "You are in an interview for the Data Engineer position on the "
    "Data Platform team at Meridian Health Systems. The role involves "
    "building and scaling pipelines for clinical analytics across 40+ "
    "hospitals. Compensation range is $135,000 to $160,000. The "
    "position is remote-friendly and based in Austin, TX.\n\n"
    "The interviewer is Dana Reeves, who manages the Data Platform "
    "team. The candidate is Sarah Chen, a data engineer with 5 years "
    "of experience at a fintech company."
)


def _extract_response_text(response: Message) -> str:
    """Pulls plain text from an API response.

    Args:
        response: The Anthropic API response message.

    Returns:
        Concatenated text content from all text blocks.
    """
    parts = []
    for block in response.content:
        if isinstance(block, TextBlock):
            parts.append(block.text)
    return "\n".join(parts)


def _log_payload(
    speaker_name: str,
    turn_number: int,
    payload: dict,
    transcript: list[dict[str, str]],
) -> None:
    """Logs the full payload being sent to the API.

    Args:
        speaker_name: Who is speaking this turn.
        turn_number: Current interview turn number.
        payload: The assembled MessagePayload.
        transcript: Transcript so far before this turn.
    """
    log.debug("\n%s", "=" * 60)
    log.debug("TURN %d: %s speaking", turn_number, speaker_name)
    log.debug("=" * 60)
    log.debug("Transcript length: %d entries", len(transcript))
    log.debug("\n--- SYSTEM PROMPT ---\n%s", payload["system"])
    log.debug("\n--- MESSAGES (%d) ---", len(payload["messages"]))
    for i, msg in enumerate(payload["messages"]):
        log.debug("  [%d] role=%s, len=%d", i, msg["role"], len(msg["content"]))
        log.debug("    %s", msg["content"][:200])
        if len(msg["content"]) > 200:
            log.debug("    ...")

    roles = [m["role"] for m in payload["messages"]]
    for i in range(1, len(roles)):
        if roles[i] == roles[i - 1]:
            log.warning(
                "ALTERNATION VIOLATION at index %d: %s follows %s",
                i, roles[i], roles[i - 1],
            )


def _log_response(
    speaker_name: str,
    turn_number: int,
    response: Message,
    text: str,
    latency: float,
) -> None:
    """Logs the API response details.

    Args:
        speaker_name: Who spoke this turn.
        turn_number: Current interview turn number.
        response: Raw API response.
        text: Extracted text from the response.
        latency: Wall time for the API call in seconds.
    """
    log.debug("\n--- RESPONSE ---")
    log.debug("  Stop reason: %s", response.stop_reason)
    log.debug(
        "  Tokens: %d in / %d out",
        response.usage.input_tokens,
        response.usage.output_tokens,
    )
    log.debug("  Latency: %.1fs", latency)
    log.debug("  Text:\n%s", text)

    log.info(
        "  Turn %d [%s]: %d tokens in, %d tokens out, %.1fs",
        turn_number,
        speaker_name,
        response.usage.input_tokens,
        response.usage.output_tokens,
        latency,
    )


async def run_interview(
    client: AsyncAnthropic,
    builder: PromptBuilder,
    config: RunConfig,
    sarah: JobSeekerProfile,
    dana: HiringManagerProfile,
    max_turns: int,
) -> list[dict[str, str]]:
    """Runs a full interview, alternating between Dana and Sarah.

    Dana speaks on odd turns, Sarah on even turns. Each turn builds the
    payload from the growing transcript, sends it to the API, and
    appends the response.

    Args:
        client: Anthropic async client.
        builder: Prompt builder instance.
        config: Simulation config with model version.
        sarah: Job seeker profile.
        dana: Hiring manager profile.
        max_turns: Total number of turns to run.

    Returns:
        The complete interview transcript.
    """
    transcript: list[dict[str, str]] = []
    total_input_tokens = 0
    total_output_tokens = 0

    for turn in range(1, max_turns + 1):
        if turn % 2 == 1:
            speaker_profile = dana
        else:
            speaker_profile = sarah

        payload = builder.build_interview_turn(
            speaker_profile=speaker_profile,
            role_context=ROLE_CONTEXT,
            transcript=transcript,
            turn_number=turn,
        )

        _log_payload(speaker_profile.name, turn, payload, transcript)

        t0 = time.monotonic()
        response = await client.messages.create(
            model=config.sonnet_model_version,
            system=payload["system"],
            messages=payload["messages"],
            max_tokens=1024,
        )
        latency = time.monotonic() - t0

        text = _extract_response_text(response)
        _log_response(speaker_profile.name, turn, response, text, latency)

        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

        transcript.append({
            "speaker": speaker_profile.name,
            "content": text,
        })

    log.info("")
    log.info("=" * 60)
    log.info("INTERVIEW SUMMARY")
    log.info("=" * 60)
    log.info("  Turns completed: %d", len(transcript))
    log.info("  Total input tokens:  %s", f"{total_input_tokens:,}")
    log.info("  Total output tokens: %s", f"{total_output_tokens:,}")

    return transcript


def _log_transcript(transcript: list[dict[str, str]]) -> None:
    """Logs the final readable transcript.

    Args:
        transcript: Complete interview transcript.
    """
    log.info("")
    log.info("=" * 60)
    log.info("FULL TRANSCRIPT")
    log.info("=" * 60)
    for i, entry in enumerate(transcript, 1):
        log.info("")
        log.info("[Turn %d] %s:", i, entry["speaker"])
        log.info("%s", entry["content"])


async def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("Set ANTHROPIC_API_KEY in .env or environment.")
        sys.exit(1)

    client = AsyncAnthropic(api_key=api_key)
    config = build_config()
    builder = PromptBuilder(config)
    sarah = build_sarah()
    dana = build_dana()

    max_turns = config.interview_turn_ceiling

    log.info("=" * 60)
    log.info("INTERVIEW VALIDATION: Sarah Chen x Dana Reeves")
    log.info("Role: Data Engineer, Meridian Health Systems")
    log.info("Max turns: %d (ceiling from config)", max_turns)
    log.info("=" * 60)
    log.info("")

    t0 = time.monotonic()
    transcript = await run_interview(
        client, builder, config, sarah, dana, max_turns
    )
    elapsed = time.monotonic() - t0

    _log_transcript(transcript)

    log.info("")
    log.info("Wall time: %.1fs", elapsed)
    log.info("Full log written to %s", LOG_FILE)


if __name__ == "__main__":
    asyncio.run(main())