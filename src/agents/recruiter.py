"""Recruiter agent with tools for screening, forwarding, and communication.

Manages the hiring pipeline between jobseekers and hiring managers:
screens incoming applications, forwards promising candidates, sends
status updates, and nudges unresponsive hiring managers.
"""

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, NamedTuple

from anthropic import AsyncAnthropic

from agents.base import BaseAgent
from schemas.company import JobPosting
from schemas.config import RunConfig
from schemas.interview import InterviewData, format_transcript
from schemas.profiles import RecruiterProfile
from schemas.records import ApplicationRecord, EventEntry, RecruiterHMMessage
from schemas.states import RecruiterState
from tools.definitions import (
    FORWARD_TO_HIRING_MANAGER,
    MANAGE_CANDIDATE_COMMUNICATION,
    NUDGE_HIRING_MANAGER,
    SCREEN_APPLICATIONS,
    recruiter_tools,
)

logger = logging.getLogger(__name__)

_STUB_MESSAGE = "This action is not available right now."


class _RoleHistory(NamedTuple):
    """Feedback and forwarding history for a single posting."""

    lines: list[str]
    has_feedback: bool


class RecruiterAgent(BaseAgent):
    """Represents a recruiter managing hiring pipelines.

    Screens incoming applications, forwards promising candidates to
    hiring managers, communicates with candidates about their status,
    and nudges hiring managers when they are unresponsive. Operates as
    the bridge between seekers and hiring managers.

    Attributes:
        hm_messages_sent: Messages produced during the turn for the
            engine to persist after the turn completes.
        events_created: Events produced during the turn, typically
            status notifications directed at seekers.
    """

    def __init__(
        self,
        profile: RecruiterProfile,
        config: RunConfig,
        state: RecruiterState,
        postings: list[JobPosting],
        applications: list[ApplicationRecord],
        hm_messages: list[RecruiterHMMessage],
        job_seeker_info: dict[str, dict[str, str]],
        *,
        client: AsyncAnthropic | None = None,
    ) -> None:
        """Initializes the recruiter with pre-fetched simulation data.

        Args:
            profile: The recruiter's immutable identity, company
                assignment, and workload.
            config: Simulation-wide parameters.
            state: The recruiter's mutable state including pipeline
                and screening metrics.
            postings: Job postings this recruiter is responsible for.
            applications: Applications submitted to this recruiter's
                postings.
            hm_messages: History of messages exchanged with hiring
                managers.
            job_seeker_info: Maps seeker_id to a dict containing "name"
                and "resume" for candidates who applied.
            client: Anthropic async client. Injected for testing.
        """
        super().__init__(profile=profile, config=config, client=client)
        self._recruiter = profile
        self._state = state
        self._postings = {p.id: p for p in postings}
        self._applications = {a.id: a for a in applications}
        self._hm_messages = hm_messages
        self._job_seeker_info = job_seeker_info
        self._screened_application_ids: set[str] = set()

        self.hm_messages_sent: list[RecruiterHMMessage] = []
        self.events_created: list[EventEntry] = []

    def get_tools(self) -> list[dict[str, Any]]:
        """Returns all recruiter tool definitions for the Anthropic API."""
        return recruiter_tools()

    def build_context(self) -> str:
        """Assembles the recruiter's current situation for the user message.

        Combines profile metadata, posting pipeline, HM relationship
        history, and accumulated state into a single context string.

        Returns:
            Formatted context string for injection into the user message.
        """
        sections = [
            self._build_role_header(),
            self._build_posting_summary(),
            self._build_pipeline_summary(),
            self._build_hm_relationship_summary(),
            self._build_history_section(),
        ]
        return "\n".join(section for section in sections if section)

    async def handle_tool_call(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Dispatches a tool call to the appropriate handler.

        Implemented tools execute their full logic. Stubbed tools return
        a message indicating the action is not yet available.

        Args:
            tool_name: Name of the tool the model invoked.
            tool_input: Parameters the model passed to the tool.

        Returns:
            Result string fed back to the model as tool output.
        """
        _Handler = Callable[[dict[str, Any]], Awaitable[str]]
        handlers: dict[str, _Handler] = {
            SCREEN_APPLICATIONS: self._screen_applications,
            FORWARD_TO_HIRING_MANAGER: self._forward_to_hiring_manager,
            MANAGE_CANDIDATE_COMMUNICATION: self._manage_candidate_communication,
            NUDGE_HIRING_MANAGER: self._nudge_hiring_manager,
        }
        handler = handlers.get(tool_name)
        if handler:
            return await handler(tool_input)

        logger.info("[%s] stubbed tool called: %s", self.profile.id, tool_name)
        return _STUB_MESSAGE

    async def screen_candidate(self, interaction: Any) -> str:
        """Produce a pre-interview screening assessment of a candidate.

        Validates the interaction, assembles candidate and role data,
        then layers in HM feedback history and a signal strength
        indicator. Called during the recruiter's regular turn when
        screening applications.

        Args:
            interaction: A dict containing at minimum an
            "application_id" key referencing a known application.

        Returns:
            Multi-line screening assessment string, or a short message
            if the interaction data is missing or invalid.
        """
        if not isinstance(interaction, dict):
            return "No interaction data to evaluate."

        application_id = interaction.get("application_id")
        if not application_id or application_id not in self._applications:
            return "No matching application found for evaluation."

        app = self._applications[application_id]
        posting = self._postings.get(app.posting_id)
        job_seeker = self._job_seeker_info.get(app.job_seeker_id, {})
        resume_text = job_seeker.get("resume")

        sections = self._format_evaluation_header(app, posting, job_seeker)
        role_history = self._collect_role_history(app.posting_id)
        sections.extend(role_history.lines)
        sections.append(
            self._compute_signal_strength(resume_text, role_history.has_feedback, posting)
        )

        return "\n".join(sections)

    async def assess_interview(self, data: InterviewData) -> str:
        """Produce a post-interview candidate assessment.

        Evaluates the candidate through the recruiter's lens,
        considering experience level and knowledge of what the
        hiring manager values. A junior recruiter may focus on
        surface-level signals while a senior one picks up on
        subtler fit indicators.

        Args:
            data: Interview transcript, role context, and candidate
                name.

        Returns:
            Written assessment ending with a
            ``DECISION: ADVANCE/REJECT/UNDECIDED`` line.
        """
        system = self._prompt_builder.build_system_message(self.profile)

        p = self._recruiter
        transcript_text = format_transcript(data.transcript)

        user_content = (
            f"You just finished a screening interview with "
            f"{data.other_party_name} for the following role:\n\n"
            f"{data.role_context}\n\n"
            f"Transcript:\n\n{transcript_text}\n\n"
            f"Your experience level: {p.experience_level}. "
            f"Current workload: {p.current_workload} open roles.\n\n"
            "Write your assessment of the candidate. Cover:\n"
            "- Communication quality and professionalism\n"
            "- Apparent fit for the role requirements\n"
            "- Culture fit signals based on your knowledge of the "
            "company\n"
            "- Any red flags or standout qualities\n\n"
            "Then state your decision on its own final line in "
            "exactly this format:\n"
            "DECISION: ADVANCE or REJECT or UNDECIDED"
        )

        response = await self.call_api(system, [{"role": "user", "content": user_content}])
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text
        return text.strip()

    def _format_evaluation_header(
        self,
        app: ApplicationRecord,
        posting: JobPosting | None,
        job_seeker: dict[str, str],
    ) -> list[str]:
        """Formats the candidate identity, role alignment, and resume.

        Args:
            app: The application being evaluated.
            posting: The posting applied to, if found.
            job_seeker: Dict with "name" and optional "resume" keys.

        Returns:
            Lines covering candidate name, role, status, requirements,
            and resume preview.
        """
        candidate_name = job_seeker.get("name", "Unknown")
        lines = [
            "Candidate Fit Assessment",
            f"  Candidate: {candidate_name}",
            f"  Role: {posting.title if posting else 'Unknown'}",
            f"  Application status: {app.status}",
        ]

        if posting:
            lines.append(f"  Seniority: {posting.seniority}")
            lines.append(f"  Requirements: {', '.join(posting.requirements)}")

        resume_text = job_seeker.get("resume")
        if resume_text:
            lines.append(f"  Resume preview: {resume_text[:500]}")
        else:
            lines.append("  Resume: not available (weak signal)")

        return lines

    def _collect_role_history(self, posting_id: str) -> _RoleHistory:
        """Collects HM feedback and forwarding history for a posting.

        Args:
            posting_id: The posting to gather history for.

        Returns:
            A _RoleHistory with formatted lines and a flag indicating
            whether any HM feedback exists.
        """
        lines: list[str] = []

        feedback = [
            m
            for m in self._hm_messages
            if m.message_type == "feedback" and m.posting_id == posting_id
        ]
        if feedback:
            lines.append("  HM feedback patterns for this role:")
            for fb in feedback[-3:]:
                lines.append(f"    - {fb.content[:150]}")
        else:
            lines.append("  HM feedback: none yet for this role (no signal on preferences)")

        forwards = [
            m
            for m in self._hm_messages
            if m.message_type == "candidate_forward" and m.posting_id == posting_id
        ]
        if forwards:
            lines.append(f"  Prior forwards for this role: {len(forwards)}")

        return _RoleHistory(lines=lines, has_feedback=bool(feedback))

    def _compute_signal_strength(
        self,
        resume_text: str | None,
        has_feedback: bool,
        posting: JobPosting | None,
    ) -> str:
        """Computes a data quality label based on available signals.

        Args:
            resume_text: The candidate's resume, or None.
            has_feedback: Whether any HM feedback exists for the role.
            posting: The posting, used to check for requirements.

        Returns:
            A single formatted line with the signal strength label.
        """
        signals = [
            bool(resume_text),
            has_feedback,
            bool(posting and posting.requirements),
        ]
        count = sum(signals)
        labels = {0: "very weak", 1: "weak", 2: "moderate", 3: "strong"}
        return f"  Data quality: {labels[count]} ({count}/3 signals available)"

    def _build_role_header(self) -> str:
        """Builds the recruiter's identity and workload header.

        Returns:
            Formatted string with company, experience, and workload.
        """
        p = self._recruiter
        return (
            f"Company: {p.company_id}\n"
            f"Experience level: {p.experience_level}\n"
            f"Current workload: {p.current_workload} open roles\n"
        )

    def _build_posting_summary(self) -> str:
        """Builds a summary of assigned postings with application counts.

        Returns:
            Formatted string listing each posting and its pending
            application count, or a note if no postings are assigned.
        """
        if not self._postings:
            return "Your assigned postings:\n  No postings assigned.\n"

        lines = ["Your assigned postings:"]
        for posting in self._postings.values():
            pending_count = sum(
                1
                for a in self._applications.values()
                if a.posting_id == posting.id and a.status == "pending"
            )
            lines.append(
                f"- [{posting.id}] {posting.title} ({posting.seniority}) "
                f"-- {pending_count} pending application(s), "
                f"status: {posting.status}"
            )
        lines.append("")
        return "\n".join(lines)

    def _build_pipeline_summary(self) -> str:
        """Builds aggregate pipeline counts and active entries.

        Returns:
            Formatted string with status breakdown, active pipeline,
            and aggregate screening totals.
        """
        sections = [
            self._format_status_counts(),
            self._format_active_pipeline(),
            self._format_aggregate_metrics(),
        ]
        return "\n".join(section for section in sections if section)

    def _format_status_counts(self) -> str:
        """Formats application counts grouped by status.

        Returns:
            Formatted status breakdown, or empty string if there
            are no applications.
        """
        status_counts: dict[str, int] = {}
        for app in self._applications.values():
            status_counts[app.status] = status_counts.get(app.status, 0) + 1

        if not status_counts:
            return ""

        lines = ["Application pipeline summary:"]
        for status, count in status_counts.items():
            lines.append(f"  {status}: {count}")
        lines.append("")
        return "\n".join(lines)

    def _format_active_pipeline(self) -> str:
        """Formats current pipeline entries from agent state.

        Returns:
            Formatted active pipeline list, or empty string if the
            pipeline is empty.
        """
        if not self._state.current_pipeline:
            return ""

        lines = [f"Active pipeline ({len(self._state.current_pipeline)}):"]
        for entry in self._state.current_pipeline:
            label = entry.get("posting_title", entry.get("posting_id", "?"))
            lines.append(f"- {label}: {entry.get('status', 'unknown')}")
        lines.append("")
        return "\n".join(lines)

    def _format_aggregate_metrics(self) -> str:
        """Formats overall screening, forwarding, and rejection totals.

        Returns:
            Single summary line with totals, or empty string if no
            screening activity has occurred.
        """
        s = self._state
        if s.total_screened == 0 and s.total_forwarded == 0:
            return ""

        return (
            f"Overall: {s.total_screened} screened, "
            f"{s.total_forwarded} forwarded, "
            f"{s.total_rejected} rejected\n"
        )

    def _build_hm_relationship_summary(self) -> str:
        """Builds a summary of hiring manager interactions.

        Includes forwarding volume and recent feedback excerpts to
        give the recruiter context on each HM relationship.

        Returns:
            Formatted string with forward counts, recent feedback,
            and the list of assigned hiring managers.
        """
        sections = []
        p = self._recruiter

        forwards = [m for m in self._hm_messages if m.message_type == "candidate_forward"]
        feedback = [m for m in self._hm_messages if m.message_type == "feedback"]

        if forwards:
            sections.append(f"Candidates forwarded to HMs: {len(forwards)}")
        if feedback:
            sections.append("Recent HM feedback:")
            for fb in feedback[-5:]:
                sections.append(f"  - {fb.content[:200]}")
            sections.append("")

        sections.append(f"Hiring managers you work with: {', '.join(p.hiring_manager_ids)}")
        sections.append("")
        return "\n".join(sections)

    def _build_history_section(self) -> str:
        """Builds compressed history and recent events from agent state.

        Returns:
            Formatted string with prior context summary and a list
            of recent event descriptions.
        """
        sections = []
        s = self._state

        if s.compressed_history:
            sections.extend(["Previous context:", s.compressed_history, ""])

        if s.recent_events:
            sections.append("Recent events:")
            for event in s.recent_events:
                sections.append(f"- {event.get('description', str(event))}")

        return "\n".join(sections)

    async def _screen_applications(self, tool_input: dict[str, Any]) -> str:
        """Filters and returns pending applications for review.

        Tracks which applications have already been counted toward
        the screened metric to avoid double-counting across multiple
        calls in the same turn.

        Args:
            tool_input: Optional "posting_id" to narrow results.

        Returns:
            Formatted listing of pending applications with candidate
            names, resumes, and role requirements.
        """
        posting_id = tool_input.get("posting_id")

        pending = [
            a
            for a in self._applications.values()
            if a.status == "pending" and (posting_id is None or a.posting_id == posting_id)
        ]

        if not pending:
            if posting_id:
                return f"No pending applications for posting '{posting_id}'."
            return "No pending applications across your postings."

        formatted = []
        for app in pending:
            posting = self._postings.get(app.posting_id)
            job_seeker = self._job_seeker_info.get(app.job_seeker_id, {})

            lines = [
                f"Application: {app.id}",
                f"  Candidate: {job_seeker.get('name', 'Unknown')}",
                f"  Applied to: {posting.title if posting else app.posting_id} ({app.posting_id})",
                f"  Round submitted: {app.round_submitted}",
            ]

            resume_text = job_seeker.get("resume", "No resume available.")
            lines.append(f"  Resume:\n{resume_text}")

            if posting:
                lines.append(f"  Role requirements: {', '.join(posting.requirements)}")

            formatted.append("\n".join(lines))

        new_ids = {a.id for a in pending} - self._screened_application_ids
        self._screened_application_ids.update(new_ids)
        self._state.total_screened += len(new_ids)

        return f"Found {len(pending)} pending application(s):\n\n" + "\n\n---\n\n".join(formatted)

    async def _forward_to_hiring_manager(self, tool_input: dict[str, Any]) -> str:
        """Forwards a candidate to the appropriate hiring manager.

        Creates a RecruiterHMMessage with the recruiter's framing and
        updates the application status to "reviewed".

        Args:
            tool_input: Must contain "application_id" and "summary".

        Returns:
            Confirmation string with the message ID, or an error if
            the application or posting is invalid.
        """
        application_id = tool_input["application_id"]
        summary = tool_input["summary"]

        app = self._applications.get(application_id)
        if not app:
            return f"No application found with ID '{application_id}'."

        posting = self._postings.get(app.posting_id)
        if not posting:
            return f"No posting found for application '{application_id}'."

        hm_id = posting.hiring_manager_id
        if not hm_id:
            return f"Posting '{app.posting_id}' has no hiring manager assigned."

        msg_id = f"hm-msg-{uuid.uuid4().hex[:8]}"
        message = RecruiterHMMessage(
            id=msg_id,
            sender_id=self.profile.id,
            receiver_id=hm_id,
            round_sent=self._state.round_number,
            content=summary,
            message_type="candidate_forward",
            posting_id=app.posting_id,
            related_application_id=application_id,
        )
        self.hm_messages_sent.append(message)

        app.status = "reviewed"
        app.status_updated_round = self._state.round_number

        self._state.total_forwarded += 1

        job_seeker = self._job_seeker_info.get(app.job_seeker_id, {})
        candidate_name = job_seeker.get("name", "Unknown")

        logger.info(
            "[%s] forwarded %s (%s) to HM %s for %s",
            self.profile.id,
            candidate_name,
            application_id,
            hm_id,
            posting.title,
        )
        return (
            f"Forwarded {candidate_name} to hiring manager {hm_id} for {posting.title} ({msg_id})."
        )

    async def _manage_candidate_communication(self, tool_input: dict[str, Any]) -> str:
        """Sends a status update or rejection to a candidate.

        Updates the application status and creates an EventEntry that
        the jobseeker will see on their next check_application_status call.

        Args:
            tool_input: Must contain "application_id", "message",
                and "new_status".

        Returns:
            Confirmation string with the event ID, or an error if
            the application is not found.
        """
        application_id = tool_input["application_id"]
        message_text = tool_input["message"]
        new_status = tool_input["new_status"]

        app = self._applications.get(application_id)
        if not app:
            return f"No application found with ID '{application_id}'."

        posting = self._postings.get(app.posting_id)
        posting_title = posting.title if posting else app.posting_id

        app.status = new_status
        app.status_updated_round = self._state.round_number

        event_id = f"evt-{uuid.uuid4().hex[:8]}"
        event = EventEntry(
            id=event_id,
            agent_id=app.job_seeker_id,
            round_number=self._state.round_number,
            event_type=f"application_{new_status}",
            details={
                "application_id": application_id,
                "posting_id": app.posting_id,
                "posting_title": posting_title,
                "message": message_text,
                "from_recruiter": self.profile.id,
            },
            created_at=datetime.now(timezone.utc),
        )
        self.events_created.append(event)

        if new_status == "rejected":
            self._state.total_rejected += 1

        job_seeker = self._job_seeker_info.get(app.job_seeker_id, {})
        candidate_name = job_seeker.get("name", "Unknown")

        logger.info(
            "[%s] sent %s to %s (%s) for %s",
            self.profile.id,
            new_status,
            candidate_name,
            application_id,
            posting_title,
        )
        return (
            f"Sent {new_status} notification to {candidate_name} for {posting_title} ({event_id})."
        )

    async def _nudge_hiring_manager(self, tool_input: dict[str, Any]) -> str:
        """Sends a nudge to a hiring manager about pending decisions.

        Validates that both the hiring manager and posting belong to
        this recruiter before creating the message.

        Args:
            tool_input: Must contain "hiring_manager_id", "posting_id",
                and "message".

        Returns:
            Confirmation string with the message ID, or an error if
            the HM or posting is not assigned to this recruiter.
        """
        hm_id = tool_input["hiring_manager_id"]
        posting_id = tool_input["posting_id"]
        message_text = tool_input["message"]

        if hm_id not in self._recruiter.hiring_manager_ids:
            return f"Hiring manager '{hm_id}' is not one of your assigned HMs."

        if posting_id not in self._postings:
            return f"Posting '{posting_id}' is not one of your assigned postings."

        msg_id = f"hm-msg-{uuid.uuid4().hex[:8]}"
        message = RecruiterHMMessage(
            id=msg_id,
            sender_id=self.profile.id,
            receiver_id=hm_id,
            round_sent=self._state.round_number,
            content=message_text,
            message_type="nudge",
            posting_id=posting_id,
        )
        self.hm_messages_sent.append(message)

        logger.info(
            "[%s] nudged HM %s about posting %s",
            self.profile.id,
            hm_id,
            posting_id,
        )
        return f"Nudge sent to hiring manager {hm_id} about {posting_id} ({msg_id})."
