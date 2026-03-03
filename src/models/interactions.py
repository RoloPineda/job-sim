"""Interaction models for applications, interviews, offers, and messages."""

from typing import Any, Literal

from pydantic import BaseModel


class ApplicationRecord(BaseModel):
    """Links a job seeker to a posting through an application.

    Tracks the full lifecycle from submission through outcome.
    """

    id: str
    seeker_id: str
    posting_id: str
    resume_version_id: str
    cover_letter: str | None = None
    round_submitted: int
    status: Literal["pending", "reviewed", "rejected", "advanced", "ghosted"] = (
        "pending"
    )
    status_updated_round: int | None = None


class InterviewRecord(BaseModel):
    """A complete interview interaction with transcript and evaluations."""

    id: str
    application_id: str
    interviewer_id: str
    interviewer_type: Literal["recruiter", "hiring_manager"]
    round: int
    transcript: list[dict[str, str]]
    interviewer_evaluation: str | None = None
    candidate_evaluation: str | None = None
    outcome: Literal["advanced", "rejected", "undecided"] = "undecided"
    turn_count: int


class OfferRecord(BaseModel):
    """An offer and any negotiation that follows."""

    id: str
    application_id: str
    round_extended: int
    base_salary: int
    total_comp: int | None = None
    role_title: str
    negotiation_history: list[dict[str, Any]] = []
    final_outcome: Literal["accepted", "declined", "negotiating"] = "negotiating"
    round_resolved: int | None = None


class RecruiterHMMessage(BaseModel):
    """Communication between a recruiter and hiring manager.

    How a recruiter frames a candidate to the HM is itself behavioral data.
    """

    id: str
    sender_id: str
    receiver_id: str
    round: int
    content: str
    message_type: Literal[
        "candidate_forward", "feedback", "nudge", "role_change_request"
    ]
    related_application_id: str | None = None
