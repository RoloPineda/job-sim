"""Jobseeker agent with tools for browsing, resume writing, and applying.

Handles the full candidate lifecycle: browsing postings, crafting
resumes, submitting applications, and eventually interviewing and
evaluating offers. Operates autonomously based on the seeker's
profile traits and evolving financial pressure.
"""

import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from anthropic import AsyncAnthropic

from agents.base import BaseAgent
from schemas.company import JobPosting
from schemas.config import RunConfig
from schemas.interview import InterviewData, format_transcript
from schemas.profiles import JobSeekerProfile
from schemas.records import ApplicationRecord, ResumeVersion
from schemas.states import JobSeekerState
from tools.definitions import (
    BROWSE_JOB_BOARD,
    SUBMIT_APPLICATION,
    WRITE_RESUME,
    job_seeker_tools,
)

logger = logging.getLogger(__name__)

_STUB_MESSAGE = "This action is not available right now."


def _format_posting(posting: JobPosting, current_round: int) -> str:
    """Format a posting's visible fields as readable text.

    Hidden attributes (is_ghost, actual_budget) are excluded so the
    agent only sees what a real candidate would see.

    Args:
        posting: The job posting to format.
        current_round: Current simulation round, used to compute how
            long the posting has been up.

    Returns:
        Multi-line formatted string with posting details.
    """
    days_up = current_round - posting.round_posted
    if days_up == 0:
        age_label = "Posted today"
    elif days_up == 1:
        age_label = "Posted 1 day ago"
    else:
        age_label = f"Posted {days_up} days ago"

    lines = [
        f"[{posting.id}] {posting.title} at {posting.company_name}",
        f"  Department: {posting.department}",
        f"  Location: {posting.location} (Remote: {'Yes' if posting.remote else 'No'})",
        f"  Seniority: {posting.seniority}",
    ]
    if posting.salary_range_low is not None and posting.salary_range_high is not None:
        lines.append(
            f"  Salary: ${posting.salary_range_low:,} - "
            f"${posting.salary_range_high:,}"
        )
    elif posting.salary_range_low is not None:
        lines.append(f"  Salary: from ${posting.salary_range_low:,}")
    else:
        lines.append("  Salary: Not listed")
    lines.append(f"  {age_label}")
    lines.append(f"  Requirements: {', '.join(posting.requirements)}")
    lines.append(f"  Description: {posting.description}")
    return "\n".join(lines)


def _format_work_history(profile: JobSeekerProfile) -> str:
    """Format work history entries for the context prompt.

    Args:
        profile: The seeker profile containing work history.

    Returns:
        Formatted work history string, or a note if empty.
    """
    if not profile.work_history:
        return "No prior work experience."
    entries = []
    for w in profile.work_history:
        end = "present" if w.end_year is None else f"{w.end_month}/{w.end_year}"
        header = f"- {w.title} at {w.company} ({w.start_month}/{w.start_year} to {end})"
        bullets = "\n".join(f"  {b}" for b in w.bullets)
        entries.append(f"{header}\n{bullets}" if bullets else header)
    return "\n".join(entries)


def _format_education(profile: JobSeekerProfile) -> str:
    """Format education history for the context prompt.

    Args:
        profile: The seeker profile containing education history.

    Returns:
        Comma-separated education entries.
    """
    return ", ".join(
        f"{e.degree} from {e.school} ({e.year})" for e in profile.education_history
    )


class JobSeekerAgent(BaseAgent):
    """Agent representing a person searching for a job.

    Carries a resume that evolves over time, tracks application history
    and outcomes, and makes autonomous decisions about where to apply,
    how much effort to invest, and how selective to be.

    Attributes:
        resume_versions: Resume versions produced during the turn for
            the engine to persist after the turn completes.
        applications: Applications produced during the turn for the
            engine to persist after the turn completes.
    """

    def __init__(
        self,
        profile: JobSeekerProfile,
        config: RunConfig,
        state: JobSeekerState,
        postings: list[JobPosting],
        *,
        client: AsyncAnthropic | None = None,
    ) -> None:
        """Initializes the seeker with pre-fetched simulation data.

        Args:
            profile: The seeker's immutable identity, skills, and traits.
            config: Simulation-wide parameters.
            state: The seeker's mutable state including financial
                position, preferences, pipeline, and resume.
            postings: Visible job postings the seeker can browse.
            recruiter_map: Maps posting_id to the recruiter_id
                responsible for that posting. Used when creating
                ApplicationRecords.
            client: Anthropic async client. Injected for testing.
        """
        super().__init__(profile=profile, config=config, client=client)
        self._seeker = profile
        self._state = state
        self._postings = {p.id: p for p in postings}

        self.resume_versions: list[ResumeVersion] = []
        self.applications: list[ApplicationRecord] = []

    def get_tools(self) -> list[dict[str, Any]]:
        """Return all jobseeker tool definitions."""
        return job_seeker_tools()

    def build_context(self) -> str:
        """Assemble the seeker's current situation for the user message.

        Pulls from the profile (skills, work history) and mutable state
        (finances, preferences, resume, pipeline) to give the model a
        complete picture of where this person stands.

        Returns:
            Formatted context string for injection into the user message.
        """
        p = self._seeker
        s = self._state

        months_remaining = s.savings // s.burn_rate if s.burn_rate else "unknown"

        sections = [
            f"Your skills: {', '.join(p.perceived_skills)}",
            f"Experience: {p.experience_years} years",
            f"Education: {_format_education(p)}",
            f"Location: {p.location} "
            f"(flexibility: {s.location_flexibility}, "
            f"remote preference: {s.remote_preference})",
            "",
            "Work history:",
            _format_work_history(p),
            "",
            "Financial situation:",
            f"- Savings: ${s.savings:,}",
            f"- Monthly expenses: ${s.burn_rate:,}",
            f"- Estimated runway: {months_remaining} months",
            "",
            f"Target roles: {', '.join(s.target_roles)} ({s.target_seniority} level)",
            f"Target compensation: ${s.target_comp_low:,} - ${s.target_comp_high:,}",
        ]

        if s.current_resume:
            sections.extend(["", "Your current resume:", s.current_resume])
        else:
            sections.extend(["", "You haven't written a resume yet."])

        if s.current_pipeline:
            sections.append("")
            sections.append(f"Active applications ({len(s.current_pipeline)}):")
            for app in s.current_pipeline:
                sections.append(
                    f"- {app.get('posting_title', app.get('posting_id', '?'))}: "
                    f"{app.get('status', 'pending')}"
                )

        if s.total_applications > 0:
            sections.append("")
            sections.append(
                f"Overall: {s.total_applications} applications submitted, "
                f"{s.total_rejections} rejections"
            )

        if s.compressed_history:
            sections.extend(["", "Previous context:", s.compressed_history])

        if s.recent_events:
            sections.append("")
            sections.append("Recent events:")
            for event in s.recent_events:
                sections.append(f"- {event.get('description', str(event))}")

        return "\n".join(sections)

    async def handle_tool_call(
        self, tool_name: str, tool_input: dict[str, Any]
    ) -> str:
        """Dispatch a tool call to the appropriate handler.

        Args:
            tool_name: Name of the tool the model invoked.
            tool_input: Parameters the model passed to the tool.

        Returns:
            Result string fed back to the model as tool output.
        """
        _Handler = Callable[[dict[str, Any]], Awaitable[str]]
        handlers: dict[str, _Handler] = {
            BROWSE_JOB_BOARD: self._browse_job_board,
            WRITE_RESUME: self._write_resume,
            SUBMIT_APPLICATION: self._submit_application,
        }
        handler = handlers.get(tool_name)
        if handler:
            return await handler(tool_input)

        logger.info(
            "[%s] stubbed tool called: %s", self.profile.id, tool_name
        )
        return _STUB_MESSAGE

    async def assess_interview(self, data: InterviewData) -> str:
        """Produce a post-interview self-assessment.

        Reflects on the interview from the candidate's perspective,
        incorporating financial pressure, target preferences, and
        perceived skills. A seeker with low savings and few options
        will assess even a mediocre interview more favorably than
        one with a comfortable runway.

        Args:
            data: Interview transcript, role context, and interviewer
                name.

        Returns:
            The seeker's written self-assessment.
        """
        system = self._prompt_builder.build_system_message(self.profile)

        s = self._state
        months_remaining = s.savings // s.burn_rate if s.burn_rate else "unknown"
        transcript_text = format_transcript(data.transcript)

        user_content = (
            f"You just finished an interview with {data.other_party_name} "
            f"for the following role:\n\n{data.role_context}\n\n"
            f"Transcript:\n\n{transcript_text}\n\n"
            f"Your current situation: ${s.savings:,} in savings with "
            f"${s.burn_rate:,}/month in expenses ({months_remaining} "
            f"months runway). You're targeting "
            f"{', '.join(s.target_roles)} roles at the "
            f"{s.target_seniority} level, "
            f"${s.target_comp_low:,}-${s.target_comp_high:,}.\n\n"
            "Reflect on how the interview went from your perspective. "
            "Cover:\n"
            "- How well you were able to present your skills and "
            "experience\n"
            "- Your impression of the interviewer and the role\n"
            "- Whether this opportunity still interests you and why\n"
            "- Anything you wish you had said or done differently"
        )

        response = await self.call_api(
            system, [{"role": "user", "content": user_content}]
        )
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text
        return text.strip()

    async def _browse_job_board(self, tool_input: dict[str, Any]) -> str:
        """Filter and return visible postings matching the criteria.

        Args:
            tool_input: Optional filters for role_type, seniority,
                location, and min_salary.

        Returns:
            Formatted listing of matching postings.
        """
        matches = list(self._postings.values())

        role_type = tool_input.get("role_type")
        if role_type:
            role_lower = role_type.lower()
            matches = [p for p in matches if role_lower in p.title.lower()]

        seniority = tool_input.get("seniority")
        if seniority:
            matches = [p for p in matches if p.seniority == seniority]

        location = tool_input.get("location")
        if location:
            loc_lower = location.lower()
            if loc_lower == "remote":
                matches = [p for p in matches if p.remote]
            else:
                matches = [p for p in matches if loc_lower in p.location.lower()]

        min_salary = tool_input.get("min_salary")
        if min_salary is not None:
            matches = [
                p for p in matches
                if p.salary_range_high is not None
                and p.salary_range_high >= min_salary
            ]

        if not matches:
            return "No postings match your filters."

        current_round = self._state.round_number
        formatted = [_format_posting(p, current_round) for p in matches]
        return f"Found {len(matches)} posting(s):\n\n" + "\n\n".join(formatted)

    async def _write_resume(self, tool_input: dict[str, Any]) -> str:
        """Create a new resume version and update the agent's state.

        Args:
            tool_input: Must contain "resume_text". Optionally
                "target_posting_id".

        Returns:
            Confirmation string with the resume version ID.
        """
        resume_text = tool_input["resume_text"]
        target_posting_id = tool_input.get("target_posting_id")

        trigger: Literal["initial", "general_rewrite", "tailored"]
        if target_posting_id:
            trigger = "tailored"
        elif self._state.current_resume:
            trigger = "general_rewrite"
        else:
            trigger = "initial"

        version_id = f"resume-{uuid.uuid4().hex[:8]}"
        version = ResumeVersion(
            id=version_id,
            seeker_id=self.profile.id,
            round_created=self._state.round_number,
            full_text=resume_text,
            trigger=trigger,
            target_posting_id=target_posting_id,
            state_summary_at_creation=self._state_summary(),
        )
        self.resume_versions.append(version)
        self._state.current_resume = resume_text

        logger.info(
            "[%s] wrote resume %s (trigger=%s)",
            self.profile.id,
            version_id,
            trigger,
        )
        if target_posting_id:
            return f"Resume saved ({version_id}), tailored for {target_posting_id}."
        return f"Resume saved ({version_id})."

    async def _submit_application(self, tool_input: dict[str, Any]) -> str:
        """Submit an application to a posting using the current resume.

        Args:
            tool_input: Must contain "posting_id".

        Returns:
            Confirmation string with the application ID, or an error
            if the resume is missing or the posting is invalid.
        """
        posting_id = tool_input["posting_id"]

        if not self._state.current_resume:
            return "You need to write a resume before applying."

        posting = self._postings.get(posting_id)
        if not posting:
            return f"No posting found with ID '{posting_id}'."

        if posting.status != "open":
            return f"Posting '{posting_id}' is no longer accepting applications."

        resume_version_id = (
            self.resume_versions[-1].id
            if self.resume_versions
            else "pre-existing"
        )

        app_id = f"app-{uuid.uuid4().hex[:8]}"
        application = ApplicationRecord(
            id=app_id,
            job_seeker_id=self.profile.id,
            posting_id=posting_id,
            recruiter_id=None, # This is saved by the engine when saving the record
            resume_version_id=resume_version_id,
            round_submitted=self._state.round_number,
        )
        self.applications.append(application)

        self._state.current_pipeline.append(
            {
                "application_id": app_id,
                "posting_id": posting_id,
                "posting_title": posting.title,
                "company_id": posting.company_id,
                "status": "pending",
                "round_submitted": self._state.round_number,
            }
        )
        self._state.total_applications += 1

        logger.info(
            "[%s] submitted application %s to %s (%s)",
            self.profile.id,
            app_id,
            posting_id,
            posting.title,
        )
        return f"Application submitted to {posting.title} ({app_id})."

    def _state_summary(self) -> str:
        """Generate a brief summary of the agent's current situation.

        Used as metadata on resume and cover letter versions to capture
        behavioral context at the time of writing.

        Returns:
            Single-line summary with round, application count, and savings.
        """
        s = self._state
        return (
            f"Round {s.round_number}, "
            f"{s.total_applications} applications submitted, "
            f"${s.savings:,} savings remaining"
        )