"""Tests for agent models."""

import pytest
from pydantic import ValidationError

from src.models.agents import (
    AgentProfile,
    AgentState,
    HiringManagerProfile,
    JobSeekerProfile,
    RecruiterProfile,
)


class TestAgentProfile:
    """Tests for the base AgentProfile model."""

    def test_valid_profile(self) -> None:
        profile = AgentProfile(
            id="a1",
            agent_type="job_seeker",
            name="Alice",
            disposition="optimistic and persistent",
            backstory="Recent CS grad from a state university",
        )
        assert profile.name == "Alice"
        assert profile.agent_type == "job_seeker"

    def test_invalid_agent_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgentProfile(
                id="a1",
                agent_type="interviewer",
                name="Bob",
                disposition="calm",
                backstory="Veteran",
            )

    def test_serialization_roundtrip(self) -> None:
        profile = AgentProfile(
            id="a1",
            agent_type="recruiter",
            name="Bob",
            disposition="calm",
            backstory="Veteran recruiter",
        )
        data = profile.model_dump()
        restored = AgentProfile(**data)
        assert restored == profile

    def test_missing_required_field(self) -> None:
        with pytest.raises(ValidationError):
            AgentProfile(
                id="a1",
                agent_type="job_seeker",
                name="Alice",
                disposition="optimistic",
            )


class TestJobSeekerProfile:
    """Tests for JobSeekerProfile model."""

    @pytest.fixture()
    def seeker_data(self) -> dict:
        return {
            "id": "js1",
            "agent_type": "job_seeker",
            "name": "Alice",
            "disposition": "optimistic",
            "backstory": "Recent grad",
            "actual_skills": ["Python", "ML"],
            "perceived_skills": ["Python", "ML", "System Design"],
            "experience_years": 3,
            "target_role": "ML Engineer",
            "target_seniority": "mid",
            "target_comp_low": 120000,
            "target_comp_high": 160000,
            "location_flexibility": "flexible",
            "financial_runway": 12,
            "communication_ability": "strong",
            "self_awareness": "overconfident",
        }

    def test_valid_seeker(self, seeker_data: dict) -> None:
        seeker = JobSeekerProfile(**seeker_data)
        assert seeker.actual_skills == ["Python", "ML"]
        assert seeker.financial_runway == 12
        assert seeker.agent_type == "job_seeker"

    def test_inherits_agent_profile(self, seeker_data: dict) -> None:
        seeker = JobSeekerProfile(**seeker_data)
        assert isinstance(seeker, AgentProfile)

    def test_actual_and_perceived_skills_are_independent(
        self, seeker_data: dict
    ) -> None:
        """The model stores both lists independently with no enforced relationship.

        This is intentional: the gap between actual and perceived skills
        drives simulation behavior (e.g. overconfident agents apply to
        roles they're unqualified for).
        """
        seeker = JobSeekerProfile(**seeker_data)
        assert seeker.actual_skills != seeker.perceived_skills
        assert seeker.actual_skills == ["Python", "ML"]
        assert seeker.perceived_skills == ["Python", "ML", "System Design"]

    def test_invalid_location_flexibility_rejected(self, seeker_data: dict) -> None:
        seeker_data["location_flexibility"] = "anywhere"
        with pytest.raises(ValidationError):
            JobSeekerProfile(**seeker_data)

    def test_invalid_communication_ability_rejected(self, seeker_data: dict) -> None:
        seeker_data["communication_ability"] = "excellent"
        with pytest.raises(ValidationError):
            JobSeekerProfile(**seeker_data)

    def test_invalid_self_awareness_rejected(self, seeker_data: dict) -> None:
        seeker_data["self_awareness"] = "delusional"
        with pytest.raises(ValidationError):
            JobSeekerProfile(**seeker_data)

    def test_inherited_fields_accessible(self, seeker_data: dict) -> None:
        seeker = JobSeekerProfile(**seeker_data)
        assert seeker.name == "Alice"
        assert seeker.disposition == "optimistic"
        assert seeker.backstory == "Recent grad"
        assert seeker.id == "js1"

    def test_serialization_roundtrip(self, seeker_data: dict) -> None:
        seeker = JobSeekerProfile(**seeker_data)
        data = seeker.model_dump()
        restored = JobSeekerProfile(**data)
        assert restored == seeker

    def test_json_roundtrip(self, seeker_data: dict) -> None:
        seeker = JobSeekerProfile(**seeker_data)
        json_str = seeker.model_dump_json()
        restored = JobSeekerProfile.model_validate_json(json_str)
        assert restored == seeker

    def test_empty_skills_lists(self, seeker_data: dict) -> None:
        seeker_data["actual_skills"] = []
        seeker_data["perceived_skills"] = []
        seeker = JobSeekerProfile(**seeker_data)
        assert seeker.actual_skills == []
        assert seeker.perceived_skills == []

    def test_zero_experience_years(self, seeker_data: dict) -> None:
        seeker_data["experience_years"] = 0
        seeker = JobSeekerProfile(**seeker_data)
        assert seeker.experience_years == 0

    def test_zero_financial_runway(self, seeker_data: dict) -> None:
        seeker_data["financial_runway"] = 0
        seeker = JobSeekerProfile(**seeker_data)
        assert seeker.financial_runway == 0

    def test_wrong_type_for_experience_years(self, seeker_data: dict) -> None:
        seeker_data["experience_years"] = "three"
        with pytest.raises(ValidationError):
            JobSeekerProfile(**seeker_data)

    def test_negative_experience_years_rejected(self, seeker_data: dict) -> None:
        seeker_data["experience_years"] = -1
        with pytest.raises(ValidationError):
            JobSeekerProfile(**seeker_data)

    def test_negative_financial_runway_rejected(self, seeker_data: dict) -> None:
        seeker_data["financial_runway"] = -5
        with pytest.raises(ValidationError):
            JobSeekerProfile(**seeker_data)

    def test_negative_comp_rejected(self, seeker_data: dict) -> None:
        seeker_data["target_comp_low"] = -50000
        with pytest.raises(ValidationError):
            JobSeekerProfile(**seeker_data)

    def test_comp_low_exceeds_high_rejected(self, seeker_data: dict) -> None:
        seeker_data["target_comp_low"] = 200000
        seeker_data["target_comp_high"] = 150000
        with pytest.raises(ValidationError):
            JobSeekerProfile(**seeker_data)

    def test_equal_comp_range_allowed(self, seeker_data: dict) -> None:
        seeker_data["target_comp_low"] = 150000
        seeker_data["target_comp_high"] = 150000
        seeker = JobSeekerProfile(**seeker_data)
        assert seeker.target_comp_low == seeker.target_comp_high


class TestRecruiterProfile:
    """Tests for RecruiterProfile model."""

    @pytest.fixture()
    def recruiter_data(self) -> dict:
        return {
            "id": "r1",
            "agent_type": "recruiter",
            "name": "Bob",
            "disposition": "efficient and direct",
            "backstory": "10 years in tech recruiting",
            "company_id": "c1",
            "hiring_manager_ids": ["hm1", "hm2"],
            "assigned_posting_ids": ["p1", "p2", "p3"],
            "experience_level": "senior",
            "current_workload": 3,
        }

    def test_valid_recruiter(self, recruiter_data: dict) -> None:
        recruiter = RecruiterProfile(**recruiter_data)
        assert recruiter.company_id == "c1"
        assert len(recruiter.assigned_posting_ids) == 3

    def test_inherits_agent_profile(self, recruiter_data: dict) -> None:
        recruiter = RecruiterProfile(**recruiter_data)
        assert isinstance(recruiter, AgentProfile)

    def test_invalid_experience_level_rejected(self, recruiter_data: dict) -> None:
        recruiter_data["experience_level"] = "principal"
        with pytest.raises(ValidationError):
            RecruiterProfile(**recruiter_data)

    def test_inherited_fields_accessible(self, recruiter_data: dict) -> None:
        recruiter = RecruiterProfile(**recruiter_data)
        assert recruiter.name == "Bob"
        assert recruiter.agent_type == "recruiter"
        assert recruiter.disposition == "efficient and direct"

    def test_serialization_roundtrip(self, recruiter_data: dict) -> None:
        recruiter = RecruiterProfile(**recruiter_data)
        data = recruiter.model_dump()
        restored = RecruiterProfile(**data)
        assert restored == recruiter

    def test_empty_posting_ids(self, recruiter_data: dict) -> None:
        recruiter_data["assigned_posting_ids"] = []
        recruiter_data["hiring_manager_ids"] = []
        recruiter = RecruiterProfile(**recruiter_data)
        assert recruiter.assigned_posting_ids == []
        assert recruiter.hiring_manager_ids == []

    def test_zero_workload(self, recruiter_data: dict) -> None:
        recruiter_data["current_workload"] = 0
        recruiter = RecruiterProfile(**recruiter_data)
        assert recruiter.current_workload == 0

    def test_negative_workload_rejected(self, recruiter_data: dict) -> None:
        recruiter_data["current_workload"] = -1
        with pytest.raises(ValidationError):
            RecruiterProfile(**recruiter_data)


class TestHiringManagerProfile:
    """Tests for HiringManagerProfile model."""

    @pytest.fixture()
    def hm_data(self) -> dict:
        return {
            "id": "hm1",
            "agent_type": "hiring_manager",
            "name": "Carol",
            "disposition": "thorough but slow to decide",
            "backstory": "Former engineer turned manager",
            "company_id": "c1",
            "team_size": 6,
            "team_situation": "understaffed",
            "management_style": "detailed_feedback",
            "technical_bar": "Strong system design, pragmatic coding",
            "interview_capacity_per_round": 2,
            "past_hiring_description": "Hired 3 engineers last year",
        }

    def test_valid_hm(self, hm_data: dict) -> None:
        hm = HiringManagerProfile(**hm_data)
        assert hm.team_situation == "understaffed"
        assert hm.interview_capacity_per_round == 2

    def test_inherits_agent_profile(self, hm_data: dict) -> None:
        hm = HiringManagerProfile(**hm_data)
        assert isinstance(hm, AgentProfile)

    def test_invalid_team_situation_rejected(self, hm_data: dict) -> None:
        hm_data["team_situation"] = "overstaffed"
        with pytest.raises(ValidationError):
            HiringManagerProfile(**hm_data)

    def test_invalid_management_style_rejected(self, hm_data: dict) -> None:
        hm_data["management_style"] = "laissez_faire"
        with pytest.raises(ValidationError):
            HiringManagerProfile(**hm_data)

    def test_inherited_fields_accessible(self, hm_data: dict) -> None:
        hm = HiringManagerProfile(**hm_data)
        assert hm.name == "Carol"
        assert hm.agent_type == "hiring_manager"
        assert hm.backstory == "Former engineer turned manager"

    def test_serialization_roundtrip(self, hm_data: dict) -> None:
        hm = HiringManagerProfile(**hm_data)
        data = hm.model_dump()
        restored = HiringManagerProfile(**data)
        assert restored == hm

    def test_zero_interview_capacity(self, hm_data: dict) -> None:
        hm_data["interview_capacity_per_round"] = 0
        hm = HiringManagerProfile(**hm_data)
        assert hm.interview_capacity_per_round == 0

    def test_negative_team_size_rejected(self, hm_data: dict) -> None:
        hm_data["team_size"] = -1
        with pytest.raises(ValidationError):
            HiringManagerProfile(**hm_data)

    def test_negative_interview_capacity_rejected(self, hm_data: dict) -> None:
        hm_data["interview_capacity_per_round"] = -2
        with pytest.raises(ValidationError):
            HiringManagerProfile(**hm_data)


class TestAgentState:
    """Tests for AgentState model."""

    def test_defaults(self) -> None:
        state = AgentState()
        assert state.round_number == 0
        assert state.compressed_history == ""
        assert state.recent_events == []
        assert state.current_pipeline == []
        assert state.current_resume is None
        assert state.metrics == {}
        assert state.last_reflection is None

    def test_populated_state(self) -> None:
        state = AgentState(
            round_number=5,
            compressed_history="Applied to 3 jobs, rejected from 2",
            recent_events=[
                {"type": "application_submitted", "posting_id": "p4"},
                {"type": "rejection_received", "posting_id": "p3"},
            ],
            current_pipeline=[{"posting_id": "p4", "status": "pending"}],
            current_resume="Experienced ML engineer...",
            metrics={"rejection_rate": 0.67, "total_applications": 3},
            last_reflection="Need to broaden my search",
        )
        assert state.round_number == 5
        assert len(state.recent_events) == 2
        assert state.metrics["rejection_rate"] == 0.67

    def test_serialization_roundtrip(self) -> None:
        state = AgentState(
            round_number=3,
            recent_events=[{"type": "interview", "round": 3}],
            metrics={"count": 1},
        )
        data = state.model_dump()
        restored = AgentState(**data)
        assert restored == state

    def test_json_roundtrip(self) -> None:
        state = AgentState(
            round_number=5,
            compressed_history="Summary of events",
            current_resume="A resume",
            metrics={"rate": 0.5},
        )
        json_str = state.model_dump_json()
        restored = AgentState.model_validate_json(json_str)
        assert restored == state

    def test_mutable_defaults_are_independent(self) -> None:
        """Each instance gets its own mutable default lists/dicts."""
        state1 = AgentState()
        state2 = AgentState()
        state1.recent_events.append({"type": "test"})
        state1.metrics["count"] = 1
        assert state2.recent_events == []
        assert state2.metrics == {}

    def test_deeply_nested_structures_survive_roundtrip(self) -> None:
        """State is serialized to JSON in Postgres, so deeply nested
        structures in recent_events and metrics must survive the trip."""
        state = AgentState(
            round_number=10,
            recent_events=[
                {
                    "type": "interview_completed",
                    "details": {
                        "posting": {
                            "id": "p1",
                            "title": "SWE",
                            "company": {"name": "Acme"},
                        },
                        "scores": [0.8, 0.9, 0.75],
                        "evaluations": {
                            "interviewer": {"rating": 4, "notes": "Strong"},
                            "candidate": {"rating": 3, "notes": "Mixed signals"},
                        },
                    },
                },
            ],
            current_pipeline=[
                {
                    "posting_id": "p1",
                    "stages": [
                        {"name": "applied", "round": 1},
                        {"name": "phone_screen", "round": 3, "outcome": "advanced"},
                        {"name": "onsite", "round": 5, "interviewers": ["hm1", "r1"]},
                    ],
                },
            ],
            metrics={
                "by_company": {
                    "c1": {"apps": 2, "rejections": 1},
                    "c2": {"apps": 1, "rejections": 0},
                },
                "weekly_trend": [0.1, 0.3, 0.5, 0.4],
            },
        )
        json_str = state.model_dump_json()
        restored = AgentState.model_validate_json(json_str)
        assert restored == state
        # Verify deep access still works after roundtrip
        event_details = restored.recent_events[0]["details"]
        assert event_details["posting"]["company"]["name"] == "Acme"
        assert event_details["evaluations"]["interviewer"]["rating"] == 4
        assert restored.current_pipeline[0]["stages"][2]["interviewers"] == [
            "hm1",
            "r1",
        ]
        assert restored.metrics["by_company"]["c1"]["rejections"] == 1
