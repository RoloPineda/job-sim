"""Transactional record schemas for the job simulation.

These schemas capture events, interactions, and state changes that occur
during a simulation run. All records are append-only unless explicitly
noted as mutable.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from schemas.types import AgentType


class ApplicationRecord(BaseModel):
    """A jobseeker's application to a posting.

    Tracks the full lifecycle from submission through outcome. Links
    back to the seeker, posting, recruiter, and the specific resume
    and cover letter versions used.

    Attributes:
        id: Unique application identifier.
        job_seeker_id: Job seeker who submitted the application.
        posting_id: Posting the application targets.
        recruiter_id: Recruiter responsible for reviewing this
            application.
        resume_version_id: Resume version submitted with the
            application.
        cover_letter_version_id: Cover letter submitted, or None if
            the jobseeker did not write one.
        round_submitted: Simulation round when the application was
            sent.
        status: Current state of the application. Ghosted is distinct
            from rejected since the jobseeker never receives a response.
        status_updated_round: Round when the status last changed, or
            None if still pending.
    """

    id: str
    job_seeker_id: str
    posting_id: str
    # recruiter id is optional since background companies won't have a recruiter
    recruiter_id: str | None = None
    resume_version_id: str
    cover_letter_version_id: str | None = None
    round_submitted: int = Field(ge=0)
    status: Literal["pending", "reviewed", "rejected", "advanced", "ghosted"] = "pending"
    status_updated_round: int | None = None


class ResumeVersion(BaseModel):
    """A single version of a jobseeker's resume.

    Append-only. Every call to write_resume creates a new row. The
    trigger field records why the rewrite happened, which is itself
    behavioral data.

    Attributes:
        id: Unique resume version identifier.
        job_seeker_id: Jobseeker who wrote this resume.
        round_created: Simulation round when this version was written.
        full_text: Complete resume text.
        trigger: What caused the rewrite.
        target_posting_id: Posting this resume was tailored for, or
            None if not targeting a specific role.
        state_summary_at_creation: Freeform summary of the agent's
            state when the resume was written, for behavioral context.
    """

    id: str
    job_seeker_id: str
    round_created: int = Field(ge=0)
    full_text: str
    trigger: Literal["initial", "general_rewrite", "tailored"]
    target_posting_id: str | None = None
    state_summary_at_creation: str


class CoverLetterVersion(BaseModel):
    """A single version of a jobseeker's cover letter.

    Append-only. Unlike resumes, cover letters are always tied to a
    specific posting.

    Attributes:
        id: Unique cover letter version identifier.
        job_seeker_id: Jobseeker who wrote this cover letter.
        round_created: Simulation round when this was written.
        full_text: Complete cover letter text.
        trigger: What caused the write.
        target_posting_id: Posting this cover letter was written for.
            Required since cover letters are always tied to a specific
            application.
        state_summary_at_creation: Freeform summary of the agent's
            state when the cover letter was written.
    """

    id: str
    job_seeker_id: str
    round_created: int = Field(ge=0)
    full_text: str
    trigger: Literal["initial", "tailored"]
    target_posting_id: str
    state_summary_at_creation: str


class InterviewRecord(BaseModel):
    """A complete interview interaction between a candidate and interviewer.

    Stores the full transcript plus both agents' independent evaluations.
    The transcript is populated turn by turn as the simulation engine
    alternates between interviewer and candidate agents. Turn count is
    bounded by interview_turn_floor and interview_turn_ceiling in
    RunConfig.

    Attributes:
        id: Unique interview identifier.
        application_id: Application that led to this interview.
        interviewer_id: Agent who conducted the interview.
        interviewer_type: Whether the interviewer is a recruiter or
            hiring manager.
        round_scheduled: Simulation round when the interview was
            booked. The gap between this and round_conducted shows
            how long the candidate waited.
        round_conducted: Simulation round when the interview took
            place.
        transcript: List of speaker/content dicts capturing the full
            conversation. Stored as JSON in Postgres with array order
            preserved.
        interviewer_evaluation: Interviewer's assessment of the
            candidate, generated independently after the transcript
            is complete.
        candidate_evaluation: Candidate's assessment of the interview
            experience, generated independently after the transcript
            is complete.
        outcome: Result of the interview. Ghosting is handled at the
            application level, not here.
    """

    id: str
    application_id: str
    interviewer_id: str
    interviewer_type: Literal["recruiter", "hiring_manager"]
    round_scheduled: int = Field(ge=0)
    round_conducted: int = Field(ge=0)
    transcript: list[dict[str, str]] = []
    interviewer_evaluation: str | None = None
    candidate_evaluation: str | None = None
    outcome: Literal["advanced", "rejected", "undecided"] = "undecided"


class OfferRecord(BaseModel):
    """An offer extended to a candidate and any negotiation that follows.

    Tracks the full negotiation lifecycle from initial offer through
    resolution. Negotiation history captures each move with the
    reasoning behind it.

    Attributes:
        id: Unique offer identifier.
        application_id: Application that led to this offer.
        round_extended: Simulation round when the offer was made.
        base_salary: Core compensation being negotiated, in yearly
            dollars.
        additional_benefits: Optional freeform text covering equity,
            bonus, signing bonus, relocation, or anything beyond base.
            Not structured for now. Plan to break out into structured
            fields later if agents make interesting comp tradeoffs.
        total_comp: Full package value when calculable, or None.
        negotiation_history: List of dicts capturing each move. Each
            entry includes the round, which party made the move, the
            proposed amount, and their reasoning. Stored as JSON in
            Postgres.
        final_outcome: Current state of the offer.
        round_resolved: Round when the offer was accepted or declined,
            or None if still negotiating.
    """

    id: str
    application_id: str
    round_extended: int = Field(ge=0)
    base_salary: int = Field(gt=0)
    additional_benefits: str | None = None
    total_comp: int | None = None
    negotiation_history: list[dict[str, Any]] = []
    final_outcome: Literal["accepted", "declined", "negotiating"] = "negotiating"
    round_resolved: int | None = None


class RecruiterHMMessage(BaseModel):
    """A message between a recruiter and hiring manager.

    Captures internal communication about candidates and roles. How a
    recruiter frames a candidate to the hiring manager is itself
    behavioral data worth analyzing.

    Attributes:
        id: Unique message identifier.
        sender_id: Agent who sent the message.
        receiver_id: Agent who received the message.
        round_sent: Simulation round when the message was sent.
        content: Freeform text generated by the LLM.
        message_type: Purpose of the message.
        posting_id: Posting this message relates to.
        related_application_id: Application this message is about, or
            None if the message is about the role in general.
    """

    id: str
    sender_id: str
    receiver_id: str
    round_sent: int = Field(ge=0)
    content: str
    message_type: Literal["candidate_forward", "feedback", "nudge", "role_change_request"]
    posting_id: str
    related_application_id: str | None = None


class StateSnapshot(BaseModel):
    """Point-in-time capture of an agent's full state.

    Written at the end of every round for every agent. Primary data
    source for tracking behavioral progression over time.

    Attributes:
        id: Unique snapshot identifier.
        agent_id: Agent this snapshot belongs to.
        agent_type: Kind of agent, included for filtering without
            joining back to the agent profile.
        round_number: Simulation round this snapshot was taken at.
        state_json: Serialized AgentState as a dict. Complete mutable
            state at this point in time.
        created_at: Timestamp for debugging and ordering.
    """

    id: str
    agent_id: str
    agent_type: AgentType
    round_number: int = Field(ge=0)
    state_json: dict[str, Any]
    created_at: datetime


class ReflectionEntry(BaseModel):
    """An agent's periodic self-assessment.

    Generated by prompting the agent to reflect on its current
    situation. Captures both the prompt used and the response for
    reproducibility. Primary source of quotable content for analysis.

    Attributes:
        id: Unique reflection identifier.
        agent_id: Agent who produced this reflection.
        agent_type: Kind of agent, included for filtering convenience.
        round_number: Simulation round when the reflection was
            generated.
        prompt_used: Full reflection prompt sent to the LLM.
        response: The agent's self-assessment in its own words.
        context_summary: Summary of the agent's state when the
            reflection was generated.
    """

    id: str
    agent_id: str
    agent_type: AgentType
    round_number: int = Field(ge=0)
    prompt_used: str
    response: str
    context_summary: str


class EventEntry(BaseModel):
    """Generic event log entry for any simulation occurrence.

    Catch-all for everything that happens during a simulation run.
    The typed records capture structured detail for specific
    interactions, while EventEntry captures everything at a high
    level for timelines and debugging.

    Attributes:
        id: Unique event identifier.
        agent_id: Agent this event relates to, or None for
            system-level events like a posting expiring.
        round_number: Simulation round when this event occurred.
        event_type: What happened (e.g., application_submitted,
            rejection_sent, interview_scheduled, offer_extended,
            posting_closed, resume_updated, tool_called).
        details: Event-specific data. Structure varies by event type.
        created_at: Timestamp for ordering and debugging.
    """

    id: str
    agent_id: str | None = None
    round_number: int = Field(ge=0)
    event_type: str
    details: dict[str, Any] = {}
    created_at: datetime
