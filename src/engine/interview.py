"""Interview orchestrator for multi-turn conversations between agents.

Manages the full lifecycle of a simulated interview: alternating turns
between interviewer and candidate, respecting turn floor and ceiling
from config, collecting the transcript, then calling assess_interview()
on both agents for post-interview assessments. Returns everything the
engine needs to persist the interview record.
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from typing import Any, Literal

from anthropic import AsyncAnthropic

from agents.base import BaseAgent
from engine.prompt_builder import PromptBuilder
from schemas.company import JobPosting
from schemas.config import RunConfig
from schemas.interview import InterviewData

logger = logging.getLogger(__name__)

_OUTCOME_MAP: dict[str, Literal["advanced", "rejected", "undecided"]] = {
    "ADVANCE": "advanced",
    "REJECT": "rejected",
    "UNDECIDED": "undecided",
}


@dataclass
class InterviewResult:
    """Complete output of an interview for the engine to persist.

    Attributes:
        transcript: Ordered list of speaker turns. Each entry has
            ``speaker`` (agent name) and ``content`` (what they said).
        interviewer_assessment: The interviewer's written assessment,
            including a DECISION line.
        candidate_assessment: The candidate's written self-assessment.
        outcome: The interviewer's parsed hiring decision.
        total_turns: Number of speaker turns in the conversation.
        api_calls: Total API calls made during the conversation loop.
            Does not include assessment calls, which are tracked by
            each agent's call_api monitoring.
        input_tokens: Total input tokens consumed during the
            conversation loop.
        output_tokens: Total output tokens consumed during the
            conversation loop.
    """

    transcript: list[dict[str, str]] = field(default_factory=list)
    interviewer_assessment: str = ""
    candidate_assessment: str = ""
    outcome: Literal["advanced", "rejected", "undecided"] = "undecided"
    total_turns: int = 0
    api_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class InterviewOrchestrator:
    """Runs a single interview between an interviewer and a candidate.

    Handles the alternating conversation loop, turn counting, and
    post-interview assessment delegation. The orchestrator owns the
    conversation mechanics; the agents own their assessment logic.

    The interviewer always speaks first. Turn count is chosen randomly
    between the configured floor and ceiling so interviews vary in
    length naturally.

    Args:
        interviewer: The recruiter or hiring manager agent conducting
            the interview.
        candidate: The job seeker agent being interviewed.
        role_context: Description of the role under discussion and any
            relevant context both parties should know.
        config: Simulation-wide parameters including turn limits and
            model versions.
        client: Anthropic async client for conversation turn API calls.
    """

    def __init__(
        self,
        interviewer: BaseAgent,
        candidate: BaseAgent,
        role_context: str,
        config: RunConfig,
        client: AsyncAnthropic,
    ) -> None:
        self._interviewer = interviewer
        self._candidate = candidate
        self._role_context = role_context
        self._config = config
        self._client = client
        self._prompt_builder = PromptBuilder(config)

    async def run(self) -> InterviewResult:
        """Execute the full interview and return results.

        Runs the conversation loop, then delegates to each agent's
        assess_interview() for post-interview assessments. The
        interviewer's assessment is parsed for a hiring decision.

        Returns:
            Complete interview result with transcript, assessments,
            outcome, and conversation usage statistics.
        """
        result = InterviewResult()

        target_turns = random.randint(
            self._config.interview_turn_floor,
            self._config.interview_turn_ceiling,
        )

        interviewer_name = self._interviewer.profile.name
        candidate_name = self._candidate.profile.name

        logger.info(
            "Starting interview: %s (interviewer) <-> %s (candidate), target %d turns",
            interviewer_name,
            candidate_name,
            target_turns,
        )

        transcript: list[dict[str, str]] = []
        speakers = [self._interviewer, self._candidate]

        for turn_number in range(1, target_turns + 1):
            speaker_index = (turn_number - 1) % 2
            speaker = speakers[speaker_index]

            content = await self._run_turn(speaker.profile, transcript, turn_number, result)
            transcript.append(
                {
                    "speaker": speaker.profile.name,
                    "content": content,
                }
            )

            logger.debug(
                "Turn %d/%d (%s): %d chars",
                turn_number,
                target_turns,
                speaker.profile.name,
                len(content),
            )

        result.transcript = transcript
        result.total_turns = len(transcript)

        interviewer_data = InterviewData(
            transcript=transcript,
            role_context=self._role_context,
            other_party_name=candidate_name,
        )
        candidate_data = InterviewData(
            transcript=transcript,
            role_context=self._role_context,
            other_party_name=interviewer_name,
        )

        interviewer_assessment, candidate_assessment = await asyncio.gather(
            self._interviewer.assess_interview(interviewer_data),
            self._candidate.assess_interview(candidate_data),
        )

        result.interviewer_assessment = interviewer_assessment
        result.candidate_assessment = candidate_assessment
        result.outcome = _parse_outcome(interviewer_assessment)

        logger.info(
            "Interview complete: %s <-> %s, %d turns, outcome=%s, "
            "%d conversation api calls, %d+%d tokens",
            interviewer_name,
            candidate_name,
            result.total_turns,
            result.outcome,
            result.api_calls,
            result.input_tokens,
            result.output_tokens,
        )

        return result

    async def _run_turn(
        self,
        speaker_profile: Any,
        transcript: list[dict[str, str]],
        turn_number: int,
        result: InterviewResult,
    ) -> str:
        """Execute a single speaker turn and return the spoken content.

        Uses the prompt builder to assemble the full API payload,
        including wrap-up cues near the turn ceiling.

        Args:
            speaker_profile: Profile of the agent whose turn it is.
            transcript: Conversation so far.
            turn_number: Current turn number (1-indexed).
            result: Running result to accumulate usage stats into.

        Returns:
            The text content of the speaker's response.
        """
        payload = self._prompt_builder.build_interview_turn(
            speaker_profile=speaker_profile,
            role_context=self._role_context,
            transcript=transcript,
            turn_number=turn_number,
        )

        response = await self._client.messages.create(
            model=self._config.sonnet_model_version,
            system=payload["system"],
            messages=payload["messages"],
            max_tokens=4096,
            temperature=self._config.temperature,
            top_p=self._config.top_p,
        )

        result.api_calls += 1
        result.input_tokens += response.usage.input_tokens
        result.output_tokens += response.usage.output_tokens

        return _extract_text(response)


def build_role_context(posting: JobPosting, interviewer_name: str, candidate_name: str) -> str:
    """Build the role context string for an interview.

    Assembles a description of the role from the posting that both
    the interviewer and candidate see at the start of the
    conversation. Intentionally omits hidden fields like is_ghost
    and actual_budget.

    Args:
        posting: The job posting being discussed.
        interviewer_name: Name of the interviewing agent.
        candidate_name: Name of the candidate agent.

    Returns:
        Formatted role context string.
    """
    remote_label = "Yes" if posting.remote else "No"

    salary_part = ""
    if posting.salary_range_low is not None and posting.salary_range_high is not None:
        salary_part = (
            f"Compensation range: ${posting.salary_range_low:,} to ${posting.salary_range_high:,}. "
        )

    return (
        f"This is an interview for the {posting.title} position in the "
        f"{posting.department} department at {posting.company_name}. "
        f"{posting.description} "
        f"Location: {posting.location} (Remote: {remote_label}). "
        f"Seniority: {posting.seniority}. "
        f"{salary_part}"
        f"Requirements: {', '.join(posting.requirements)}.\n\n"
        f"The interviewer is {interviewer_name}. "
        f"The candidate is {candidate_name}."
    )


def _parse_outcome(
    assessment: str,
) -> Literal["advanced", "rejected", "undecided"]:
    """Extract the hiring decision from the interviewer's assessment.

    Scans the assessment text from the bottom for a ``DECISION:``
    line. Falls back to ``undecided`` if the format is missing or
    unrecognized, which the engine can flag for manual review.

    Args:
        assessment: The interviewer's full assessment text.

    Returns:
        The parsed outcome.
    """
    for line in reversed(assessment.strip().splitlines()):
        cleaned = line.strip().upper()
        if cleaned.startswith("DECISION:"):
            token = cleaned.split(":", 1)[1].strip()
            outcome = _OUTCOME_MAP.get(token)
            if outcome is not None:
                return outcome
            logger.warning(
                "Unrecognized decision token '%s', defaulting to undecided",
                token,
            )
            return "undecided"
    logger.warning("No DECISION line found in interviewer assessment, defaulting to undecided")
    return "undecided"


def _extract_text(response: Any) -> str:
    """Extract concatenated text from an Anthropic API response.

    Args:
        response: The raw API response message.

    Returns:
        The concatenated text content, stripped of leading and
        trailing whitespace.
    """
    parts = []
    for block in response.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "\n".join(parts).strip()
