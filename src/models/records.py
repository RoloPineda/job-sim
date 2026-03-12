"""ORM models for transactional records.

These models capture events, interactions, and state changes that occur
during a simulation run. All records are append-only unless explicitly
noted as mutable.
"""

import uuid
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, UUIDPrimaryKeyMixin

_VALID_APPLICATION_STATUSES = ("pending", "reviewed", "rejected", "advanced", "ghosted")
_VALID_RESUME_TRIGGERS = ("initial", "general_rewrite", "tailored")
_VALID_COVER_LETTER_TRIGGERS = ("initial", "tailored")
_VALID_INTERVIEWER_TYPES = ("recruiter", "hiring_manager")
_VALID_INTERVIEW_OUTCOMES = ("advanced", "rejected", "undecided")
_VALID_OFFER_OUTCOMES = ("accepted", "declined", "negotiating")
_VALID_MESSAGE_TYPES = ("candidate_forward", "feedback", "nudge", "role_change_request")


class Application(UUIDPrimaryKeyMixin, Base):
    """A jobseeker's application to a posting.

    Tracks the full lifecycle from submission through outcome.

    Attributes:
        run_id: Simulation run this application belongs to.
        job_seeker_id: Jobseeker who submitted the application.
        posting_id: Posting the application targets.
        recruiter_id: Recruiter responsible for reviewing.
        resume_version_id: Resume version submitted with the
            application.
        cover_letter_version_id: Cover letter submitted, or None.
        round_submitted: Simulation round when submitted.
        status: Current state of the application.
        status_updated_round: Round when status last changed, or None.
        posting: The targeted job posting.
        resume_version: The resume version used.
        cover_letter_version: The cover letter version used, if any.
        interviews: Interviews spawned from this application.
        offers: Offers extended from this application.
    """

    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint(
            f"status IN {_VALID_APPLICATION_STATUSES!r}",
            name="ck_applications_status",
        ),
        CheckConstraint(
            "round_submitted >= 0",
            name="ck_applications_round_submitted",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("simulation_runs.id"), nullable=False
    )
    job_seeker_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agents.id"), nullable=False
    )
    posting_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("job_postings.id"), nullable=False
    )
    recruiter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agents.id"), nullable=False
    )
    resume_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("resume_versions.id"), nullable=False
    )
    cover_letter_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("cover_letter_versions.id")
    )
    round_submitted: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    status_updated_round: Mapped[int | None] = mapped_column(Integer)

    posting: Mapped["JobPosting"] = relationship()
    resume_version: Mapped["ResumeVersion"] = relationship()
    cover_letter_version: Mapped["CoverLetterVersion | None"] = relationship()
    interviews: Mapped[list["Interview"]] = relationship(back_populates="application")
    offers: Mapped[list["Offer"]] = relationship(back_populates="application")


class ResumeVersion(UUIDPrimaryKeyMixin, Base):
    """A single version of a jobseeker's resume.

    Append-only. Every resume write creates a new row.

    Attributes:
        run_id: Simulation run this version belongs to.
        job_seeker_id: Job seeker who wrote this resume.
        round_created: Simulation round when written.
        full_text: Complete resume text.
        trigger: What caused the rewrite.
        target_posting_id: Posting this resume was tailored for,
            or None.
        state_summary_at_creation: Agent state summary when written.
    """

    __tablename__ = "resume_versions"
    __table_args__ = (
        CheckConstraint(
            f"trigger IN {_VALID_RESUME_TRIGGERS!r}",
            name="ck_resume_versions_trigger",
        ),
        CheckConstraint(
            "round_created >= 0",
            name="ck_resume_versions_round_created",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("simulation_runs.id"), nullable=False
    )
    job_seeker_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agents.id"), nullable=False
    )
    round_created: Mapped[int] = mapped_column(Integer, nullable=False)
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)
    target_posting_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("job_postings.id")
    )
    state_summary_at_creation: Mapped[str] = mapped_column(Text, nullable=False)


class CoverLetterVersion(UUIDPrimaryKeyMixin, Base):
    """A single version of a jobseeker's cover letter.

    Append-only. Always tied to a specific posting.

    Attributes:
        run_id: Simulation run this version belongs to.
        job_seeker_id: Jobseeker who wrote this cover letter.
        round_created: Simulation round when written.
        full_text: Complete cover letter text.
        trigger: What caused the write.
        target_posting_id: Posting this cover letter was written for.
        state_summary_at_creation: Agent state summary when written.
    """

    __tablename__ = "cover_letter_versions"
    __table_args__ = (
        CheckConstraint(
            f"trigger IN {_VALID_COVER_LETTER_TRIGGERS!r}",
            name="ck_cover_letter_versions_trigger",
        ),
        CheckConstraint(
            "round_created >= 0",
            name="ck_cover_letter_versions_round_created",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("simulation_runs.id"), nullable=False
    )
    job_seeker_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agents.id"), nullable=False
    )
    round_created: Mapped[int] = mapped_column(Integer, nullable=False)
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)
    target_posting_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("job_postings.id"), nullable=False
    )
    state_summary_at_creation: Mapped[str] = mapped_column(Text, nullable=False)


class Interview(UUIDPrimaryKeyMixin, Base):
    """A complete interview interaction between candidate and interviewer.

    Stores the full transcript plus both agents' evaluations.

    Attributes:
        run_id: Simulation run this interview belongs to.
        application_id: Application that led to this interview.
        interviewer_id: Agent who conducted the interview.
        interviewer_type: Whether interviewer is recruiter or HM.
        round_scheduled: Round when the interview was booked.
        round_conducted: Round when the interview took place.
        transcript: List of speaker/content dicts as JSONB.
        interviewer_evaluation: Interviewer's assessment, or None.
        candidate_evaluation: Candidate's assessment, or None.
        outcome: Result of the interview.
        application: The application that spawned this interview.
    """

    __tablename__ = "interviews"
    __table_args__ = (
        CheckConstraint(
            f"interviewer_type IN {_VALID_INTERVIEWER_TYPES!r}",
            name="ck_interviews_interviewer_type",
        ),
        CheckConstraint(
            f"outcome IN {_VALID_INTERVIEW_OUTCOMES!r}",
            name="ck_interviews_outcome",
        ),
        CheckConstraint(
            "round_scheduled >= 0",
            name="ck_interviews_round_scheduled",
        ),
        CheckConstraint(
            "round_conducted >= 0",
            name="ck_interviews_round_conducted",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("simulation_runs.id"), nullable=False
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("applications.id"), nullable=False
    )
    interviewer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agents.id"), nullable=False
    )
    interviewer_type: Mapped[str] = mapped_column(String(20), nullable=False)
    round_scheduled: Mapped[int] = mapped_column(Integer, nullable=False)
    round_conducted: Mapped[int] = mapped_column(Integer, nullable=False)
    transcript: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    interviewer_evaluation: Mapped[str | None] = mapped_column(Text)
    candidate_evaluation: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(
        String(20), nullable=False, default="undecided"
    )

    application: Mapped["Application"] = relationship(back_populates="interviews")


class Offer(UUIDPrimaryKeyMixin, Base):
    """An offer extended to a candidate with negotiation tracking.

    Attributes:
        run_id: Simulation run this offer belongs to.
        application_id: Application that led to this offer.
        round_extended: Round when the offer was made.
        base_salary: Core compensation in yearly dollars.
        additional_benefits: Freeform equity/bonus/perks text, or None.
        total_comp: Full package value when calculable, or None.
        negotiation_history: List of move dicts as JSONB.
        final_outcome: Current state of the offer.
        round_resolved: Round when accepted or declined, or None.
        application: The application that spawned this offer.
    """

    __tablename__ = "offers"
    __table_args__ = (
        CheckConstraint(
            f"final_outcome IN {_VALID_OFFER_OUTCOMES!r}",
            name="ck_offers_final_outcome",
        ),
        CheckConstraint(
            "round_extended >= 0",
            name="ck_offers_round_extended",
        ),
        CheckConstraint(
            "base_salary > 0",
            name="ck_offers_base_salary",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("simulation_runs.id"), nullable=False
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("applications.id"), nullable=False
    )
    round_extended: Mapped[int] = mapped_column(Integer, nullable=False)
    base_salary: Mapped[int] = mapped_column(Integer, nullable=False)
    additional_benefits: Mapped[str | None] = mapped_column(Text)
    total_comp: Mapped[int | None] = mapped_column(Integer)
    negotiation_history: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    final_outcome: Mapped[str] = mapped_column(
        String(20), nullable=False, default="negotiating"
    )
    round_resolved: Mapped[int | None] = mapped_column(Integer)

    application: Mapped["Application"] = relationship(back_populates="offers")


class RecruiterHMMessage(UUIDPrimaryKeyMixin, Base):
    """A message between a recruiter and hiring manager.

    Captures internal communication about candidates and roles.

    Attributes:
        run_id: Simulation run this message belongs to.
        sender_id: Agent who sent the message.
        receiver_id: Agent who received the message.
        round_sent: Simulation round when sent.
        content: Freeform text generated by the LLM.
        message_type: Purpose of the message.
        posting_id: Posting this message relates to.
        related_application_id: Application this message is about,
            or None.
    """

    __tablename__ = "recruiter_hm_messages"
    __table_args__ = (
        CheckConstraint(
            f"message_type IN {_VALID_MESSAGE_TYPES!r}",
            name="ck_recruiter_hm_messages_message_type",
        ),
        CheckConstraint(
            "round_sent >= 0",
            name="ck_recruiter_hm_messages_round_sent",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("simulation_runs.id"), nullable=False
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agents.id"), nullable=False
    )
    receiver_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agents.id"), nullable=False
    )
    round_sent: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(30), nullable=False)
    posting_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("job_postings.id"), nullable=False
    )
    related_application_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("applications.id")
    )
