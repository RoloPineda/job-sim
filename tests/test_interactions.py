"""Tests for interaction models."""

import pytest
from pydantic import ValidationError

from src.models.interactions import (
    ApplicationRecord,
    InterviewRecord,
    OfferRecord,
    RecruiterHMMessage,
)


class TestApplicationRecord:
    """Tests for ApplicationRecord model."""

    @pytest.fixture()
    def app_data(self) -> dict:
        return {
            "id": "app1",
            "seeker_id": "js1",
            "posting_id": "p1",
            "resume_version_id": "rv1",
            "round_submitted": 2,
        }

    def test_valid_application(self, app_data: dict) -> None:
        app = ApplicationRecord(**app_data)
        assert app.seeker_id == "js1"
        assert app.round_submitted == 2

    def test_defaults(self, app_data: dict) -> None:
        app = ApplicationRecord(**app_data)
        assert app.status == "pending"
        assert app.cover_letter is None
        assert app.status_updated_round is None

    def test_with_cover_letter(self, app_data: dict) -> None:
        app_data["cover_letter"] = "I am very interested in this role..."
        app = ApplicationRecord(**app_data)
        assert app.cover_letter is not None

    def test_status_transitions(self, app_data: dict) -> None:
        for status in ("pending", "reviewed", "rejected", "advanced", "ghosted"):
            app_data["status"] = status
            app = ApplicationRecord(**app_data)
            assert app.status == status

    def test_invalid_status_rejected(self, app_data: dict) -> None:
        app_data["status"] = "withdrawn"
        with pytest.raises(ValidationError):
            ApplicationRecord(**app_data)

    def test_serialization_roundtrip(self, app_data: dict) -> None:
        app_data["cover_letter"] = "Dear hiring team..."
        app_data["status"] = "advanced"
        app_data["status_updated_round"] = 4
        app = ApplicationRecord(**app_data)
        data = app.model_dump()
        restored = ApplicationRecord(**data)
        assert restored == app

    def test_missing_required_field(self, app_data: dict) -> None:
        del app_data["seeker_id"]
        with pytest.raises(ValidationError):
            ApplicationRecord(**app_data)


class TestInterviewRecord:
    """Tests for InterviewRecord model."""

    @pytest.fixture()
    def interview_data(self) -> dict:
        return {
            "id": "int1",
            "application_id": "app1",
            "interviewer_id": "hm1",
            "interviewer_type": "hiring_manager",
            "round": 4,
            "transcript": [
                {"speaker": "interviewer", "content": "Tell me about yourself."},
                {"speaker": "candidate", "content": "I have 3 years of experience..."},
            ],
            "turn_count": 2,
        }

    def test_valid_interview(self, interview_data: dict) -> None:
        interview = InterviewRecord(**interview_data)
        assert len(interview.transcript) == 2
        assert interview.turn_count == 2

    def test_defaults(self, interview_data: dict) -> None:
        interview = InterviewRecord(**interview_data)
        assert interview.outcome == "undecided"
        assert interview.interviewer_evaluation is None
        assert interview.candidate_evaluation is None

    def test_with_evaluations(self, interview_data: dict) -> None:
        interview_data["interviewer_evaluation"] = "Strong technical skills"
        interview_data["candidate_evaluation"] = "Good culture fit"
        interview_data["outcome"] = "advanced"
        interview = InterviewRecord(**interview_data)
        assert interview.interviewer_evaluation == "Strong technical skills"
        assert interview.outcome == "advanced"

    def test_invalid_interviewer_type_rejected(self, interview_data: dict) -> None:
        interview_data["interviewer_type"] = "peer"
        with pytest.raises(ValidationError):
            InterviewRecord(**interview_data)

    def test_invalid_outcome_rejected(self, interview_data: dict) -> None:
        interview_data["outcome"] = "hired"
        with pytest.raises(ValidationError):
            InterviewRecord(**interview_data)

    def test_serialization_roundtrip(self, interview_data: dict) -> None:
        interview_data["interviewer_evaluation"] = "Good candidate"
        interview_data["candidate_evaluation"] = "Liked the team"
        interview_data["outcome"] = "advanced"
        interview = InterviewRecord(**interview_data)
        data = interview.model_dump()
        restored = InterviewRecord(**data)
        assert restored == interview

    def test_empty_transcript(self, interview_data: dict) -> None:
        interview_data["transcript"] = []
        interview_data["turn_count"] = 0
        interview = InterviewRecord(**interview_data)
        assert interview.transcript == []
        assert interview.turn_count == 0


class TestOfferRecord:
    """Tests for OfferRecord model."""

    @pytest.fixture()
    def offer_data(self) -> dict:
        return {
            "id": "off1",
            "application_id": "app1",
            "round_extended": 6,
            "base_salary": 140000,
            "role_title": "Software Engineer",
        }

    def test_valid_offer(self, offer_data: dict) -> None:
        offer = OfferRecord(**offer_data)
        assert offer.base_salary == 140000
        assert offer.role_title == "Software Engineer"

    def test_defaults(self, offer_data: dict) -> None:
        offer = OfferRecord(**offer_data)
        assert offer.final_outcome == "negotiating"
        assert offer.total_comp is None
        assert offer.negotiation_history == []
        assert offer.round_resolved is None

    def test_with_negotiation(self, offer_data: dict) -> None:
        offer_data["negotiation_history"] = [
            {"round": 7, "party": "candidate", "counter": 155000},
            {"round": 7, "party": "company", "counter": 148000},
        ]
        offer_data["total_comp"] = 165000
        offer_data["final_outcome"] = "accepted"
        offer_data["round_resolved"] = 8
        offer = OfferRecord(**offer_data)
        assert len(offer.negotiation_history) == 2
        assert offer.final_outcome == "accepted"

    def test_invalid_outcome_rejected(self, offer_data: dict) -> None:
        offer_data["final_outcome"] = "expired"
        with pytest.raises(ValidationError):
            OfferRecord(**offer_data)

    def test_serialization_roundtrip(self, offer_data: dict) -> None:
        offer_data["negotiation_history"] = [{"round": 7, "counter": 150000}]
        offer_data["final_outcome"] = "accepted"
        offer_data["round_resolved"] = 8
        offer = OfferRecord(**offer_data)
        data = offer.model_dump()
        restored = OfferRecord(**data)
        assert restored == offer

    def test_zero_salary(self, offer_data: dict) -> None:
        offer_data["base_salary"] = 0
        offer = OfferRecord(**offer_data)
        assert offer.base_salary == 0

    def test_wrong_type_for_salary(self, offer_data: dict) -> None:
        offer_data["base_salary"] = "competitive"
        with pytest.raises(ValidationError):
            OfferRecord(**offer_data)


class TestRecruiterHMMessage:
    """Tests for RecruiterHMMessage model."""

    @pytest.fixture()
    def message_data(self) -> dict:
        return {
            "id": "msg1",
            "sender_id": "r1",
            "receiver_id": "hm1",
            "round": 3,
            "content": "Forwarding a strong candidate for the SWE role",
            "message_type": "candidate_forward",
        }

    def test_valid_message(self, message_data: dict) -> None:
        msg = RecruiterHMMessage(**message_data)
        assert msg.sender_id == "r1"
        assert msg.message_type == "candidate_forward"

    def test_defaults(self, message_data: dict) -> None:
        msg = RecruiterHMMessage(**message_data)
        assert msg.related_application_id is None

    def test_with_related_application(self, message_data: dict) -> None:
        message_data["related_application_id"] = "app1"
        msg = RecruiterHMMessage(**message_data)
        assert msg.related_application_id == "app1"

    def test_all_message_types(self, message_data: dict) -> None:
        for msg_type in (
            "candidate_forward",
            "feedback",
            "nudge",
            "role_change_request",
        ):
            message_data["message_type"] = msg_type
            msg = RecruiterHMMessage(**message_data)
            assert msg.message_type == msg_type

    def test_invalid_message_type_rejected(self, message_data: dict) -> None:
        message_data["message_type"] = "complaint"
        with pytest.raises(ValidationError):
            RecruiterHMMessage(**message_data)

    def test_serialization_roundtrip(self, message_data: dict) -> None:
        message_data["related_application_id"] = "app1"
        msg = RecruiterHMMessage(**message_data)
        data = msg.model_dump()
        restored = RecruiterHMMessage(**data)
        assert restored == msg
