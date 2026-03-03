"""Tests for observability models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.models.observability import (
    EventEntry,
    ModelParams,
    ReflectionEntry,
    ResumeVersion,
    RunConfig,
    ScaleParams,
    StateSnapshot,
)


class TestRunConfig:
    """Tests for RunConfig and its nested parameter models."""

    def test_all_defaults(self) -> None:
        config = RunConfig()
        assert config.model_params.temperature == 0.7
        assert config.model_params.top_p == 0.95
        assert config.context_params.compression_frequency == 5
        assert config.context_params.recent_history_window == 3
        assert config.context_params.max_context_tokens == 150000
        assert config.simulation_structure.interview_turn_floor == 6
        assert config.simulation_structure.interview_turn_ceiling == 12
        assert config.market_params.ghost_job_percentage == 0.15
        assert config.scale_params.num_seekers == 10
        assert config.scale_params.total_rounds == 20

    def test_override_nested_params(self) -> None:
        config = RunConfig(
            model_params=ModelParams(temperature=0.5),
            scale_params=ScaleParams(num_seekers=20, total_rounds=50),
        )
        assert config.model_params.temperature == 0.5
        # Other defaults preserved
        assert config.model_params.top_p == 0.95
        assert config.scale_params.num_seekers == 20
        assert config.scale_params.total_rounds == 50

    def test_agent_action_order(self) -> None:
        config = RunConfig()
        assert config.simulation_structure.agent_action_order == [
            "job_seeker",
            "recruiter",
            "hiring_manager",
        ]

    def test_serialization_roundtrip(self) -> None:
        config = RunConfig()
        data = config.model_dump()
        restored = RunConfig(**data)
        assert restored == config

    def test_json_roundtrip(self) -> None:
        config = RunConfig(
            model_params=ModelParams(temperature=0.3),
            scale_params=ScaleParams(total_rounds=100),
        )
        json_str = config.model_dump_json()
        restored = RunConfig.model_validate_json(json_str)
        assert restored == config


class TestStateSnapshot:
    """Tests for StateSnapshot model."""

    def test_valid_snapshot(self) -> None:
        snapshot = StateSnapshot(
            agent_id="js1",
            agent_type="job_seeker",
            round_number=5,
            state_json={"round_number": 5, "metrics": {"apps": 3}},
        )
        assert snapshot.agent_id == "js1"
        assert snapshot.state_json["round_number"] == 5

    def test_created_at_auto_set(self) -> None:
        snapshot = StateSnapshot(
            agent_id="js1",
            agent_type="job_seeker",
            round_number=1,
            state_json={},
        )
        assert isinstance(snapshot.created_at, datetime)

    def test_explicit_created_at(self) -> None:
        ts = datetime(2025, 1, 15, 10, 30)
        snapshot = StateSnapshot(
            agent_id="js1",
            agent_type="job_seeker",
            round_number=1,
            state_json={},
            created_at=ts,
        )
        assert snapshot.created_at == ts

    def test_serialization_roundtrip(self) -> None:
        snapshot = StateSnapshot(
            agent_id="r1",
            agent_type="recruiter",
            round_number=3,
            state_json={"metrics": {"screened": 5}},
        )
        data = snapshot.model_dump()
        restored = StateSnapshot(**data)
        assert restored == snapshot

    def test_empty_state_json(self) -> None:
        snapshot = StateSnapshot(
            agent_id="js1",
            agent_type="job_seeker",
            round_number=0,
            state_json={},
        )
        assert snapshot.state_json == {}


class TestResumeVersion:
    """Tests for ResumeVersion model."""

    @pytest.fixture()
    def resume_data(self) -> dict:
        return {
            "id": "rv1",
            "seeker_id": "js1",
            "round_created": 1,
            "full_text": "Experienced ML engineer with 3 years...",
            "trigger": "initial",
            "state_summary_at_creation": "Round 1, no applications yet",
        }

    def test_valid_resume(self, resume_data: dict) -> None:
        rv = ResumeVersion(**resume_data)
        assert rv.trigger == "initial"
        assert rv.target_posting_id is None

    def test_tailored_resume(self, resume_data: dict) -> None:
        resume_data["trigger"] = "tailored"
        resume_data["target_posting_id"] = "p3"
        rv = ResumeVersion(**resume_data)
        assert rv.trigger == "tailored"
        assert rv.target_posting_id == "p3"

    def test_all_triggers(self, resume_data: dict) -> None:
        for trigger in ("initial", "general_rewrite", "tailored", "desperate_overhaul"):
            resume_data["trigger"] = trigger
            rv = ResumeVersion(**resume_data)
            assert rv.trigger == trigger

    def test_invalid_trigger_rejected(self, resume_data: dict) -> None:
        resume_data["trigger"] = "minor_tweak"
        with pytest.raises(ValidationError):
            ResumeVersion(**resume_data)

    def test_serialization_roundtrip(self, resume_data: dict) -> None:
        resume_data["trigger"] = "tailored"
        resume_data["target_posting_id"] = "p2"
        rv = ResumeVersion(**resume_data)
        data = rv.model_dump()
        restored = ResumeVersion(**data)
        assert restored == rv

    def test_missing_required_field(self, resume_data: dict) -> None:
        del resume_data["full_text"]
        with pytest.raises(ValidationError):
            ResumeVersion(**resume_data)


class TestReflectionEntry:
    """Tests for ReflectionEntry model."""

    def test_valid_reflection(self) -> None:
        entry = ReflectionEntry(
            id="ref1",
            agent_id="js1",
            agent_type="job_seeker",
            round_number=6,
            prompt_used="Reflect on your job search so far.",
            response="I've been applying broadly but should focus more.",
            context_summary="3 applications, 2 rejections, 1 pending",
        )
        assert entry.round_number == 6
        assert "focus more" in entry.response

    def test_serialization_roundtrip(self) -> None:
        entry = ReflectionEntry(
            id="ref1",
            agent_id="hm1",
            agent_type="hiring_manager",
            round_number=9,
            prompt_used="Reflect on hiring progress.",
            response="Pipeline is thin.",
            context_summary="2 candidates reviewed",
        )
        data = entry.model_dump()
        restored = ReflectionEntry(**data)
        assert restored == entry

    def test_missing_required_field(self) -> None:
        with pytest.raises(ValidationError):
            ReflectionEntry(
                id="ref1",
                agent_id="js1",
                agent_type="job_seeker",
                round_number=6,
                prompt_used="Reflect.",
                # missing response and context_summary
            )


class TestEventEntry:
    """Tests for EventEntry model."""

    def test_valid_event(self) -> None:
        event = EventEntry(
            id="ev1",
            agent_id="js1",
            round_number=3,
            event_type="application_submitted",
            details={"posting_id": "p1", "resume_version_id": "rv1"},
        )
        assert event.event_type == "application_submitted"
        assert event.details["posting_id"] == "p1"

    def test_defaults(self) -> None:
        event = EventEntry(
            id="ev2",
            round_number=1,
            event_type="round_started",
        )
        assert event.agent_id is None
        assert event.details == {}
        assert isinstance(event.created_at, datetime)

    def test_system_event_without_agent(self) -> None:
        """System-level events have no agent_id."""
        event = EventEntry(
            id="ev3",
            round_number=1,
            event_type="posting_expired",
            details={"posting_id": "p5"},
        )
        assert event.agent_id is None

    def test_serialization_roundtrip(self) -> None:
        event = EventEntry(
            id="ev1",
            agent_id="js1",
            round_number=3,
            event_type="application_submitted",
            details={"posting_id": "p1"},
        )
        data = event.model_dump()
        restored = EventEntry(**data)
        assert restored == event

    def test_json_roundtrip_with_datetime(self) -> None:
        """Datetime fields survive JSON serialization."""
        ts = datetime(2025, 6, 15, 12, 0, 0)
        event = EventEntry(
            id="ev1",
            round_number=1,
            event_type="round_started",
            created_at=ts,
        )
        json_str = event.model_dump_json()
        restored = EventEntry.model_validate_json(json_str)
        assert restored.created_at == ts

    def test_nested_details_dict(self) -> None:
        """Details dict can contain nested structures."""
        event = EventEntry(
            id="ev1",
            round_number=1,
            event_type="complex_event",
            details={
                "posting": {"id": "p1", "title": "SWE"},
                "scores": [0.8, 0.9, 0.75],
            },
        )
        assert event.details["posting"]["id"] == "p1"
        assert len(event.details["scores"]) == 3
