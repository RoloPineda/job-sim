"""Hiring manager agent with tools for candidate review and feedback.

Makes final decisions on candidates forwarded by recruiters. Reviews
candidates, provides feedback to recruiters on pipeline quality, and
rejects candidates with reasoning that helps calibrate future screening.
"""

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from anthropic import AsyncAnthropic

from agents.base import BaseAgent
from schemas.company import JobPosting
from schemas.config import RunConfig
from schemas.interview import InterviewData, format_transcript
from schemas.profiles import HiringManagerProfile
from schemas.records import ApplicationRecord, EventEntry, RecruiterHMMessage
from schemas.states import HiringManagerState
from tools.definitions import (
    ADVANCE_CANDIDATE,
    GIVE_FEEDBACK_TO_RECRUITER,
    REJECT_CANDIDATE,
    REVIEW_FORWARDED_CANDIDATES,
    hiring_manager_tools,
)

logger = logging.getLogger(__name__)

_STUB_MESSAGE = "This action is not available right now."


class HiringManagerAgent(BaseAgent):
    """Agent representing a hiring manager who makes candidate decisions.

    Reviews candidates forwarded by recruiters, provides feedback on
    pipeline quality, and rejects candidates with reasoning that flows
    back to the recruiter. The hiring manager's feedback_clarity trait
    affects how useful its feedback is, which in turn shapes recruiter
    screening over time.

    Attributes:
        hm_messages_sent: Messages produced during the turn for the
            engine to persist after the turn completes.
        events_created: Events produced during the turn, typically
            rejection or advance notifications directed at seekers.
    """

    def __init__(
        self,
        profile: HiringManagerProfile,
        config: RunConfig,
        state: HiringManagerState,
        postings: list[JobPosting],
        applications: list[ApplicationRecord],
        recruiter_messages: list[RecruiterHMMessage],
        seeker_info: dict[str, dict[str, str]],
        recruiter_info: dict[str, str],
        *,
        client: AsyncAnthropic | None = None,
    ) -> None:
        """Initializes the hiring manager with pre-fetched simulation data.

        Args:
            profile: The HM's immutable identity, team context, and
                decision-making traits.
            config: Simulation-wide parameters.
            state: The HM's mutable state including interview and
                decision metrics.
            postings: Job postings this HM is responsible for.
            applications: Applications that have been forwarded to
                this HM (status "reviewed" or "advanced").
            recruiter_messages: Full message history with recruiters,
                including forwards, feedback, and nudges.
            seeker_info: Maps seeker_id to a dict containing "name"
                and "resume" for forwarded candidates.
            recruiter_info: Maps recruiter_id to recruiter name for
                addressing feedback.
            client: Anthropic async client. Injected for testing.
        """
        super().__init__(profile=profile, config=config, client=client)
        self._hm = profile
        self._state = state
        self._postings = {p.id: p for p in postings}
        self._applications = {a.id: a for a in applications}
        self._recruiter_messages = recruiter_messages
        self._seeker_info = seeker_info
        self._recruiter_info = recruiter_info

        self.hm_messages_sent: list[RecruiterHMMessage] = []
        self.events_created: list[EventEntry] = []

    def get_tools(self) -> list[dict[str, Any]]:
        """Returns all hiring manager tool definitions for the Anthropic API."""
        return hiring_manager_tools()

    def build_context(self) -> str:
        """Assembles the HM's current situation for the user message.

        Combines team context, managed postings, forwarded candidates
        awaiting review, recruiter relationship history, and accumulated
        state into a single context string.

        Returns:
            Formatted context string for injection into the user message.
        """
        sections = [
            self._build_role_header(),
            self._build_posting_summary(),
            self._build_pending_candidates(),
            self._build_recruiter_relationship_summary(),
            self._build_metrics_summary(),
            self._build_history_section(),
        ]
        return "\n".join(section for section in sections if section)

    async def handle_tool_call(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Dispatches a tool call to the appropriate handler.

        Args:
            tool_name: Name of the tool the model invoked.
            tool_input: Parameters the model passed to the tool.

        Returns:
            Result string fed back to the model as tool output.
        """
        _Handler = Callable[[dict[str, Any]], Awaitable[str]]
        handlers: dict[str, _Handler] = {
            REVIEW_FORWARDED_CANDIDATES: self._review_forwarded_candidates,
            GIVE_FEEDBACK_TO_RECRUITER: self._give_feedback_to_recruiter,
            REJECT_CANDIDATE: self._reject_candidate,
            ADVANCE_CANDIDATE: self._advance_candidate,
        }
        handler = handlers.get(tool_name)
        if handler:
            return await handler(tool_input)

        logger.info("[%s] stubbed tool called: %s", self.profile.id, tool_name)
        return _STUB_MESSAGE

    async def assess_interview(self, data: InterviewData) -> str:
        """Produce a post-interview assessment of a candidate.

        Evaluates the candidate against the hiring manager's
        technical bar, team needs, and past hiring patterns. An HM
        with ``team_situation="understaffed"`` may be more willing
        to advance borderline candidates than one with a stable team.
        The ``feedback_clarity`` trait shapes how specific and
        actionable the assessment is.

        Args:
            data: Interview transcript, role context, and candidate
                name.

        Returns:
            Written assessment ending with a
            ``DECISION: ADVANCE/REJECT/UNDECIDED`` line.
        """
        system = self._prompt_builder.build_system_message(self.profile)

        p = self._hm
        transcript_text = format_transcript(data.transcript)

        user_content = (
            f"You just finished interviewing {data.other_party_name} "
            f"for the following role:\n\n{data.role_context}\n\n"
            f"Transcript:\n\n{transcript_text}\n\n"
            f"Your hiring bar: {p.technical_bar}\n"
            f"Team situation: {p.team_situation} "
            f"(team size: {p.team_size})\n"
            f"Past hiring context: {p.past_hiring_description}\n\n"
            "Write your assessment of the candidate. Cover:\n"
            "- Technical ability relative to the role requirements\n"
            "- Team fit given your current team situation\n"
            "- Communication quality and professionalism\n"
            "- Any concerns or standout moments\n\n"
            "Then state your decision on its own final line in "
            "exactly this format:\n"
            "DECISION: ADVANCE or REJECT or UNDECIDED"
        )

        response = await self.call_api(
            system, [{"role": "user", "content": user_content}]
        )
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text
        return text.strip()

    def _build_role_header(self) -> str:
        """Builds the HM's identity, team context, and hiring bar.

        Returns:
            Formatted string with company, team, and interview capacity.
        """
        p = self._hm
        return (
            f"Company: {p.company_id}\n"
            f"Team size: {p.team_size}\n"
            f"Team situation: {p.team_situation}\n"
            f"Management style: {p.management_style}\n"
            f"Interview capacity per round: {p.interview_capacity_per_round}\n"
            f"Your technical bar: {p.technical_bar}\n"
        )

    def _build_posting_summary(self) -> str:
        """Builds a summary of managed postings with candidate counts.

        Returns:
            Formatted string listing each posting and the number of
            forwarded candidates awaiting review.
        """
        if not self._postings:
            return "Your managed postings:\n  No postings assigned.\n"

        lines = ["Your managed postings:"]
        for posting in self._postings.values():
            forwarded_count = sum(
                1
                for a in self._applications.values()
                if a.posting_id == posting.id and a.status == "reviewed"
            )
            lines.append(
                f"- [{posting.id}] {posting.title} ({posting.seniority}) "
                f"-- {forwarded_count} candidate(s) awaiting review, "
                f"status: {posting.status}"
            )
        lines.append("")
        return "\n".join(lines)

    def _build_pending_candidates(self) -> str:
        """Builds a summary of candidates forwarded but not yet decided on.

        Returns:
            Formatted string with candidate names and which role they
            were forwarded for, or empty string if none pending.
        """
        pending = [a for a in self._applications.values() if a.status == "reviewed"]
        if not pending:
            return ""

        lines = [f"Candidates awaiting your decision ({len(pending)}):"]
        for app in pending:
            posting = self._postings.get(app.posting_id)
            seeker = self._seeker_info.get(app.job_seeker_id, {})
            candidate_name = seeker.get("name", "Unknown")
            role = posting.title if posting else app.posting_id

            forward = self._find_forward_message(app.id)
            framing = (
                f" -- Recruiter's take: {forward.content[:150]}" if forward else ""
            )

            lines.append(f"- {candidate_name} for {role} ({app.id}){framing}")
        lines.append("")
        return "\n".join(lines)

    def _build_recruiter_relationship_summary(self) -> str:
        """Builds a summary of recruiter interactions.

        Returns:
            Formatted string with recent message history.
        """
        sections = []

        forwards = [
            m for m in self._recruiter_messages if m.message_type == "candidate_forward"
        ]
        if forwards:
            sections.append(f"Candidates forwarded to you: {len(forwards)}")

        nudges = [m for m in self._recruiter_messages if m.message_type == "nudge"]
        if nudges:
            sections.append(f"Pending nudges from recruiters: {len(nudges)}")
            for nudge in nudges[-3:]:
                recruiter_name = self._recruiter_info.get(
                    nudge.sender_id, nudge.sender_id
                )
                sections.append(f"  - {recruiter_name}: {nudge.content[:200]}")

        own_feedback = [
            m for m in self._recruiter_messages if m.message_type == "feedback"
        ]
        if own_feedback:
            sections.append("Your recent feedback to recruiters:")
            for fb in own_feedback[-3:]:
                sections.append(f"  - {fb.content[:200]}")

        if sections:
            sections.append("")
        return "\n".join(sections)

    def _build_metrics_summary(self) -> str:
        """Formats interview and decision totals.

        Returns:
            Single summary line with totals, or empty string if no
            activity has occurred.
        """
        s = self._state
        if (
            s.interviews_conducted == 0
            and s.candidates_advanced == 0
            and s.candidates_rejected == 0
        ):
            return ""

        return (
            f"Overall: {s.interviews_conducted} interviews conducted, "
            f"{s.candidates_advanced} advanced, "
            f"{s.candidates_rejected} rejected\n"
        )

    def _build_history_section(self) -> str:
        """Builds compressed history and recent events from agent state.

        Returns:
            Formatted string with prior context summary and recent
            event descriptions.
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

    def _find_forward_message(self, application_id: str) -> RecruiterHMMessage | None:
        """Finds the recruiter's forward message for an application.

        Args:
            application_id: The application to find the forward for.

        Returns:
            The forward message, or None if not found.
        """
        for msg in self._recruiter_messages:
            if (
                msg.message_type == "candidate_forward"
                and msg.related_application_id == application_id
            ):
                return msg
        return None

    async def _review_forwarded_candidates(self, tool_input: dict[str, Any]) -> str:
        """Shows candidates forwarded by recruiters with full details.

        Includes the recruiter's framing, candidate resume, and role
        requirements so the HM can form an independent opinion.

        Args:
            tool_input: Optional "posting_id" to narrow results.

        Returns:
            Formatted listing of forwarded candidates.
        """
        posting_id = tool_input.get("posting_id")

        candidates = [
            a
            for a in self._applications.values()
            if a.status == "reviewed"
            and (posting_id is None or a.posting_id == posting_id)
        ]

        if not candidates:
            if posting_id:
                return f"No forwarded candidates for posting '{posting_id}'."
            return "No forwarded candidates across your postings."

        formatted = []
        for app in candidates:
            posting = self._postings.get(app.posting_id)
            seeker = self._seeker_info.get(app.job_seeker_id, {})
            candidate_name = seeker.get("name", "Unknown")

            lines = [
                f"Application: {app.id}",
                f"  Candidate: {candidate_name}",
                f"  Role: {posting.title if posting else app.posting_id}"
                f" ({app.posting_id})",
            ]

            if posting:
                lines.append(f"  Seniority: {posting.seniority}")
                lines.append(f"  Requirements: {', '.join(posting.requirements)}")

            forward = self._find_forward_message(app.id)
            if forward:
                recruiter_name = self._recruiter_info.get(
                    forward.sender_id, forward.sender_id
                )
                lines.append(
                    f"  Recruiter ({recruiter_name}) assessment: {forward.content}"
                )

            resume_text = seeker.get("resume", "No resume available.")
            lines.append(f"  Resume:\n{resume_text}")

            formatted.append("\n".join(lines))

        return (
            f"Found {len(candidates)} forwarded candidate(s):\n\n"
            + "\n\n---\n\n".join(formatted)
        )

    async def _give_feedback_to_recruiter(self, tool_input: dict[str, Any]) -> str:
        """Sends feedback to a recruiter about pipeline quality.

        Creates a RecruiterHMMessage of type "feedback" that the
        recruiter will see on their next turn.

        Args:
            tool_input: Must contain "recruiter_id", "posting_id",
                and "feedback".

        Returns:
            Confirmation string with the message ID, or an error if
            the posting is not managed by this HM.
        """
        recruiter_id = tool_input["recruiter_id"]
        posting_id = tool_input["posting_id"]
        feedback_text = tool_input["feedback"]

        if posting_id not in self._postings:
            return f"Posting '{posting_id}' is not one of your managed postings."

        msg_id = f"hm-msg-{uuid.uuid4().hex[:8]}"
        message = RecruiterHMMessage(
            id=msg_id,
            sender_id=self.profile.id,
            receiver_id=recruiter_id,
            round_sent=self._state.round_number,
            content=feedback_text,
            message_type="feedback",
            posting_id=posting_id,
        )
        self.hm_messages_sent.append(message)

        recruiter_name = self._recruiter_info.get(recruiter_id, recruiter_id)
        logger.info(
            "[%s] sent feedback to recruiter %s about posting %s",
            self.profile.id,
            recruiter_name,
            posting_id,
        )
        return f"Feedback sent to {recruiter_name} about {posting_id} ({msg_id})."

    async def _reject_candidate(self, tool_input: dict[str, Any]) -> str:
        """Rejects a candidate with reasoning sent back to the recruiter.

        Updates the application status, sends feedback to the recruiter
        explaining why the candidate was passed on, and creates an event
        that the seeker will see on their next status check.

        Args:
            tool_input: Must contain "application_id" and "reason".

        Returns:
            Confirmation string, or an error if the application is
            not found or not in a rejectable state.
        """
        application_id = tool_input["application_id"]
        reason = tool_input["reason"]

        app = self._applications.get(application_id)
        if not app:
            return f"No application found with ID '{application_id}'."

        if app.status not in ("reviewed", "advanced"):
            return (
                f"Application '{application_id}' has status "
                f"'{app.status}' and cannot be rejected from this state."
            )

        posting = self._postings.get(app.posting_id)
        posting_title = posting.title if posting else app.posting_id
        seeker = self._seeker_info.get(app.job_seeker_id, {})
        candidate_name = seeker.get("name", "Unknown")

        app.status = "rejected"
        app.status_updated_round = self._state.round_number
        self._state.candidates_rejected += 1

        forward = self._find_forward_message(application_id)
        recruiter_id = forward.sender_id if forward else app.recruiter_id
        if recruiter_id:
            msg_id = f"hm-msg-{uuid.uuid4().hex[:8]}"
            feedback = RecruiterHMMessage(
                id=msg_id,
                sender_id=self.profile.id,
                receiver_id=recruiter_id,
                round_sent=self._state.round_number,
                content=(f"Rejected {candidate_name} for {posting_title}: {reason}"),
                message_type="feedback",
                posting_id=app.posting_id,
                related_application_id=application_id,
            )
            self.hm_messages_sent.append(feedback)

        event_id = f"evt-{uuid.uuid4().hex[:8]}"
        event = EventEntry(
            id=event_id,
            agent_id=app.job_seeker_id,
            round_number=self._state.round_number,
            event_type="application_rejected",
            details={
                "application_id": application_id,
                "posting_id": app.posting_id,
                "posting_title": posting_title,
                "message": f"The hiring manager has decided not to move "
                f"forward with your application for {posting_title}.",
                "from_hiring_manager": self.profile.id,
            },
            created_at=datetime.now(timezone.utc),
        )
        self.events_created.append(event)

        logger.info(
            "[%s] rejected %s (%s) for %s: %s",
            self.profile.id,
            candidate_name,
            application_id,
            posting_title,
            reason[:100],
        )
        return (
            f"Rejected {candidate_name} for {posting_title}. "
            f"Reasoning sent to recruiter ({application_id})."
        )

    async def _advance_candidate(self, tool_input: dict[str, Any]) -> str:
        """Advances a forwarded candidate to the interview stage.

        Updates the application status, increments the HM's advance
        count, notifies the recruiter, and creates an event for the
        seeker. The runner detects applications with status "advanced"
        and schedules interviews automatically.

        Args:
            tool_input: Must contain "application_id".

        Returns:
            Confirmation string, or an error if the application is
            not found or not in an advanceable state.
        """
        application_id = tool_input["application_id"]

        app = self._applications.get(application_id)
        if not app:
            return f"No application found with ID '{application_id}'."

        if app.status != "reviewed":
            return (
                f"Application '{application_id}' has status "
                f"'{app.status}' and cannot be advanced. Only "
                f"'reviewed' applications can be advanced."
            )

        posting = self._postings.get(app.posting_id)
        posting_title = posting.title if posting else app.posting_id
        seeker = self._seeker_info.get(app.job_seeker_id, {})
        candidate_name = seeker.get("name", "Unknown")

        app.status = "advanced"
        app.status_updated_round = self._state.round_number
        self._state.candidates_advanced += 1

        forward = self._find_forward_message(application_id)
        recruiter_id = forward.sender_id if forward else app.recruiter_id
        if recruiter_id:
            msg_id = f"hm-msg-{uuid.uuid4().hex[:8]}"
            message = RecruiterHMMessage(
                id=msg_id,
                sender_id=self.profile.id,
                receiver_id=recruiter_id,
                round_sent=self._state.round_number,
                content=(
                    f"Moving forward with {candidate_name} for "
                    f"{posting_title}. Schedule an interview."
                ),
                message_type="feedback",
                posting_id=app.posting_id,
                related_application_id=application_id,
            )
            self.hm_messages_sent.append(message)

        event_id = f"evt-{uuid.uuid4().hex[:8]}"
        event = EventEntry(
            id=event_id,
            agent_id=app.job_seeker_id,
            round_number=self._state.round_number,
            event_type="application_advanced",
            details={
                "application_id": application_id,
                "posting_id": app.posting_id,
                "posting_title": posting_title,
                "message": (
                    f"Great news! The hiring manager wants to interview "
                    f"you for the {posting_title} position."
                ),
                "from_hiring_manager": self.profile.id,
            },
            created_at=datetime.now(timezone.utc),
        )
        self.events_created.append(event)

        logger.info(
            "[%s] advanced %s (%s) for %s to interview",
            self.profile.id,
            candidate_name,
            application_id,
            posting_title,
        )
        return (
            f"Advanced {candidate_name} for {posting_title} to "
            f"interview stage ({application_id})."
        )
