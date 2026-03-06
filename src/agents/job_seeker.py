"""Jobseeker agent with tools for browsing, resume writing, and applying.

Implements three tools for Step 1 validation: browse_job_board, write_resume,
and submit_application. Remaining tools are defined (so the model sees them)
but return a stub message until implemented.
"""

import logging
import uuid
from typing import Any

from anthropic import AsyncAnthropic

from agents.base import BaseAgent
from schemas.agents import AgentState, JobSeekerProfile
from schemas.company import JobPosting
from schemas.config import RunConfig
from schemas.records import ApplicationRecord, ResumeVersion

logger = logging.getLogger(__name__)

# Tool name constants
BROWSE_JOB_BOARD = "browse_job_board"
RESEARCH_COMPANY = "research_company"
WRITE_RESUME = "write_resume"
WRITE_COVER_LETTER = "write_cover_letter"
SUBMIT_APPLICATION = "submit_application"
CHECK_APPLICATION_STATUS = "check_application_status"
REVIEW_APPLICATION_HISTORY = "review_application_history"
RESPOND_TO_RECRUITER = "respond_to_recruiter"
DO_INTERVIEW = "do_interview"
EVALUATE_OFFER = "evaluate_offer"
NEGOTIATE_OFFER = "negotiate_offer"
ACCEPT_OFFER = "accept_offer"
DECLINE_OFFER = "decline_offer"
REFLECT = "reflect"

_STUB_MESSAGE = "This action is not available right now."

_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": BROWSE_JOB_BOARD,
        "description": (
            "View current open job postings. You can filter by role type, "
            "seniority, location, or whether the role is remote. Returns "
            "postings with whatever information the company chose to "
            "include. Some are detailed, some are vague. Not all list salary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filter_role": {
                    "type": "string",
                    "description": "Filter by job title or role type.",
                },
                "filter_seniority": {
                    "type": "string",
                    "description": (
                        "Filter by seniority level "
                        "(junior, mid, senior, lead, staff)."
                    ),
                },
                "filter_location": {
                    "type": "string",
                    "description": "Filter by location.",
                },
                "filter_remote": {
                    "type": "boolean",
                    "description": "If true, only show remote positions.",
                },
            },
        },
    },
    {
        "name": RESEARCH_COMPANY,
        "description": (
            "Look up information about a company that posted a role. "
            "Returns company size, industry, growth stage, and culture "
            "description. Helps you decide if this is somewhere you'd "
            "actually want to work."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company_id": {
                    "type": "string",
                    "description": "The ID of the company to research.",
                },
            },
            "required": ["company_id"],
        },
    },
    {
        "name": WRITE_RESUME,
        "description": (
            "Create or rewrite your resume. You can tailor it for a "
            "specific role or keep it general. This is what the employer "
            "sees first. You decide how much effort to put into each "
            "version."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "full_text": {
                    "type": "string",
                    "description": "The complete resume text.",
                },
                "trigger": {
                    "type": "string",
                    "enum": ["initial", "general_rewrite", "tailored"],
                    "description": (
                        "Why you are writing this resume: initial for your "
                        "first draft, general_rewrite to improve it broadly, "
                        "tailored to customize for a specific posting."
                    ),
                },
                "target_posting_id": {
                    "type": "string",
                    "description": (
                        "If tailoring for a specific posting, provide its ID."
                    ),
                },
            },
            "required": ["full_text", "trigger"],
        },
    },
    {
        "name": WRITE_COVER_LETTER,
        "description": (
            "Write a cover letter for a specific application. Optional. "
            "You decide whether it's worth the effort."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "full_text": {
                    "type": "string",
                    "description": "The complete cover letter text.",
                },
                "target_posting_id": {
                    "type": "string",
                    "description": "The posting this cover letter is for.",
                },
            },
            "required": ["full_text", "target_posting_id"],
        },
    },
    {
        "name": SUBMIT_APPLICATION,
        "description": (
            "Apply to a posting. Attaches your current resume and "
            "optionally a cover letter. Once submitted, you wait for a "
            "response that may or may not come."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "posting_id": {
                    "type": "string",
                    "description": "The ID of the posting to apply to.",
                },
            },
            "required": ["posting_id"],
        },
    },
    {
        "name": CHECK_APPLICATION_STATUS,
        "description": (
            "Check whether you've heard back from any pending "
            "applications. Returns updates if any exist. Silence is "
            "also information."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": REVIEW_APPLICATION_HISTORY,
        "description": (
            "Look back at your full application history. You can filter "
            "by status, company, or role type. Returns matching "
            "applications with company name, role, round applied, and "
            "current status. Useful for checking whether you've already "
            "applied somewhere, reviewing which companies never responded, "
            "or taking stock of your overall progress."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filter_status": {
                    "type": "string",
                    "description": (
                        "Filter by application status "
                        "(pending, reviewed, rejected, advanced, ghosted)."
                    ),
                },
            },
        },
    },
    {
        "name": RESPOND_TO_RECRUITER,
        "description": (
            "Reply to a message from a recruiter. Could be scheduling, "
            "answering questions, or following up."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Your reply to the recruiter.",
                },
                "recruiter_id": {
                    "type": "string",
                    "description": "The recruiter you are replying to.",
                },
            },
            "required": ["message", "recruiter_id"],
        },
    },
    {
        "name": DO_INTERVIEW,
        "description": (
            "Participate in an interview conversation with a recruiter "
            "or hiring manager. You'll be evaluated, but you're also "
            "evaluating them."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "interview_id": {
                    "type": "string",
                    "description": "The ID of the scheduled interview.",
                },
            },
            "required": ["interview_id"],
        },
    },
    {
        "name": EVALUATE_OFFER,
        "description": (
            "Review a job offer. See the compensation, benefits, role "
            "details, and decide your next step."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "offer_id": {
                    "type": "string",
                    "description": "The ID of the offer to review.",
                },
            },
            "required": ["offer_id"],
        },
    },
    {
        "name": NEGOTIATE_OFFER,
        "description": (
            "Counter an offer with different terms. You decide what to "
            "push on and how hard."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "offer_id": {
                    "type": "string",
                    "description": "The offer you are negotiating.",
                },
                "counter_salary": {
                    "type": "integer",
                    "description": "Your counter salary amount.",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Your reasoning for the counter.",
                },
            },
            "required": ["offer_id", "counter_salary", "reasoning"],
        },
    },
    {
        "name": ACCEPT_OFFER,
        "description": "Accept an offer and end your search.",
        "input_schema": {
            "type": "object",
            "properties": {
                "offer_id": {
                    "type": "string",
                    "description": "The offer to accept.",
                },
            },
            "required": ["offer_id"],
        },
    },
    {
        "name": DECLINE_OFFER,
        "description": "Turn down an offer and keep searching.",
        "input_schema": {
            "type": "object",
            "properties": {
                "offer_id": {
                    "type": "string",
                    "description": "The offer to decline.",
                },
                "reason": {
                    "type": "string",
                    "description": "Why you are declining.",
                },
            },
            "required": ["offer_id"],
        },
    },
    {
        "name": REFLECT,
        "description": (
            "Step back and assess how your search is going. Think about "
            "what's working, what isn't, and whether you need to change "
            "your approach. Runs automatically every few rounds, but you "
            "can also trigger it yourself."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


def _format_posting(posting: JobPosting, current_round: int) -> str:
    """Format a posting's visible fields as readable text.

    Hidden attributes (is_ghost, actual_budget) are excluded so the
    agent only sees what a real candidate would see.

    Args:
        posting: The job posting to format.
        current_round: Current simulation round, used to compute how
            long the posting has been up.
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
    """Format work history entries for the context prompt."""
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
    """Format education history for the context prompt."""
    return ", ".join(
        f"{e.degree} from {e.school} ({e.year})" for e in profile.education_history
    )


class JobSeekerAgent(BaseAgent):
    """Agent representing a person searching for a job.

    Carries a resume that evolves over time, tracks application history
    and outcomes, and makes autonomous decisions about where to apply,
    how much effort to invest, and how selective to be.

    Three tools are fully implemented for Step 1 validation:
    browse_job_board, write_resume, and submit_application. The remaining
    tools are visible to the model but return a stub response.

    Args:
        profile: The seeker's immutable profile with skills, preferences,
            and financial info.
        config: Simulation-wide parameters.
        state: The seeker's mutable state (pipeline, resume, history).
        postings: Visible job postings the seeker can browse.
        recruiter_map: Maps posting_id to the recruiter_id responsible
            for that posting. Used when creating ApplicationRecords.
        client: Anthropic async client. Injected for testing.
    """

    def __init__(
        self,
        profile: JobSeekerProfile,
        config: RunConfig,
        state: AgentState,
        postings: list[JobPosting],
        recruiter_map: dict[str, str],
        *,
        client: AsyncAnthropic | None = None,
    ) -> None:
        super().__init__(profile=profile, config=config, client=client)
        self._seeker = profile
        self._state = state
        self._postings = {p.id: p for p in postings}
        self._recruiter_map = recruiter_map

        # Records produced during the turn for the engine to collect
        self.resume_versions: list[ResumeVersion] = []
        self.applications: list[ApplicationRecord] = []

    def get_tools(self) -> list[dict[str, Any]]:
        """Return all jobseeker tool definitions."""
        return _TOOL_DEFINITIONS

    def build_context(self) -> str:
        """Assemble the seeker's current situation for the user message.

        Pulls from the profile (skills, preferences, financial state)
        and mutable state (resume, pipeline, history) to give the model
        a complete picture of where this person stands.
        """
        p = self._seeker
        s = self._state

        # Integer division is intentional: slight pessimism on runway is
        # realistic since people don't think in fractional months.
        months_remaining = p.savings // p.burn_rate if p.burn_rate else "unknown"

        sections = [
            # Skills and background
            f"Your skills: {', '.join(p.perceived_skills)}",
            f"Experience: {p.experience_years} years",
            f"Education: {_format_education(p)}",
            f"Location: {p.location} "
            f"(flexibility: {p.location_flexibility}, "
            f"remote preference: {p.remote_preference})",
            "",
            "Work history:",
            _format_work_history(p),
            "",
            # Financial pressure
            "Financial situation:",
            f"- Savings: ${p.savings:,}",
            f"- Monthly expenses: ${p.burn_rate:,}",
            f"- Estimated runway: {months_remaining} months",
            "",
            # Targets
            f"Target roles: {', '.join(p.target_roles)} ({p.target_seniority} level)",
            f"Target compensation: ${p.target_comp_low:,} - ${p.target_comp_high:,}",
        ]

        if s.current_resume:
            sections.extend(["", "Your current resume:", s.current_resume])
        else:
            sections.extend(["", "You haven't written a resume yet."])

        # Application pipeline
        if s.current_pipeline:
            sections.append("")
            sections.append(f"Active applications ({len(s.current_pipeline)}):")
            for app in s.current_pipeline:
                sections.append(
                    f"- {app.get('posting_title', app.get('posting_id', '?'))}: "
                    f"{app.get('status', 'pending')}"
                )

        # Metrics summary
        if s.metrics:
            total = s.metrics.get("total_applications", 0)
            rejections = s.metrics.get("rejections", 0)
            if total > 0:
                sections.append("")
                sections.append(
                    f"Overall: {total} applications submitted, "
                    f"{rejections} rejections"
                )

        # History context
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

        Implemented tools execute their full logic. Stubbed tools return
        a message indicating the action is not yet available.
        """
        handlers = {
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

    async def evaluate(self, interaction: Any) -> str:
        """Produce a post-interview self-assessment.

        Not yet implemented. Will generate the seeker's impressions of
        the interview, company, and interviewer once the interview
        engine is built.
        """
        return "Post-interview evaluation not yet implemented."

    # -- Implemented tool handlers -------------------------------------------

    async def _browse_job_board(self, tool_input: dict[str, Any]) -> str:
        """Filter and return visible postings matching the criteria."""
        matches = list(self._postings.values())

        filter_role = tool_input.get("filter_role")
        if filter_role:
            role_lower = filter_role.lower()
            matches = [p for p in matches if role_lower in p.title.lower()]

        filter_seniority = tool_input.get("filter_seniority")
        if filter_seniority:
            matches = [p for p in matches if p.seniority == filter_seniority]

        filter_location = tool_input.get("filter_location")
        if filter_location:
            loc_lower = filter_location.lower()
            matches = [p for p in matches if loc_lower in p.location.lower()]

        filter_remote = tool_input.get("filter_remote")
        if filter_remote:
            matches = [p for p in matches if p.remote]

        if not matches:
            return "No postings match your filters."

        current_round = self._state.round_number
        formatted = [_format_posting(p, current_round) for p in matches]
        return f"Found {len(matches)} posting(s):\n\n" + "\n\n".join(formatted)

    async def _write_resume(self, tool_input: dict[str, Any]) -> str:
        """Create a new resume version and update the agent's state."""
        full_text = tool_input["full_text"]
        trigger = tool_input["trigger"]
        target_posting_id = tool_input.get("target_posting_id")

        version_id = f"resume-{uuid.uuid4().hex[:8]}"
        version = ResumeVersion(
            id=version_id,
            seeker_id=self.profile.id,
            round_created=self._state.round_number,
            full_text=full_text,
            trigger=trigger,
            target_posting_id=target_posting_id,
            state_summary_at_creation=self._state_summary(),
        )
        self.resume_versions.append(version)
        self._state.current_resume = full_text

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
        """Submit an application to a posting using the current resume."""
        posting_id = tool_input["posting_id"]

        if not self._state.current_resume:
            return "You need to write a resume before applying."

        posting = self._postings.get(posting_id)
        if not posting:
            return f"No posting found with ID '{posting_id}'."

        if posting.status != "open":
            return f"Posting '{posting_id}' is no longer accepting applications."

        # Background companies have no recruiter. The engine handles
        # their applications deterministically based on company
        # parameters. Agent-backed companies route through a real
        # recruiter agent.
        recruiter_id = self._recruiter_map.get(posting_id)

        # Use the most recent resume version, or a placeholder if the
        # resume was set before this turn (e.g. loaded from state)
        resume_version_id = (
            self.resume_versions[-1].id
            if self.resume_versions
            else "pre-existing"
        )

        app_id = f"app-{uuid.uuid4().hex[:8]}"
        application = ApplicationRecord(
            id=app_id,
            seeker_id=self.profile.id,
            posting_id=posting_id,
            recruiter_id=recruiter_id,
            resume_version_id=resume_version_id,
            round_submitted=self._state.round_number,
        )
        self.applications.append(application)

        # Update pipeline state
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
        total = self._state.metrics.get("total_applications", 0)
        self._state.metrics["total_applications"] = total + 1

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
        """
        s = self._state
        p = self._seeker
        total_apps = s.metrics.get("total_applications", 0)
        return (
            f"Round {s.round_number}, "
            f"{total_apps} applications submitted, "
            f"${p.savings:,} savings remaining"
        )