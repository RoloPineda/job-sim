"""Tests for simulation run configuration schemas."""

import pytest
from pydantic import ValidationError

from src.schemas.config import RunConfig


def _make_config(**overrides):
    """Build a valid RunConfig, merging any field overrides.

    Args:
        **overrides: Any RunConfig fields to override.

    Returns:
        A fully constructed RunConfig.
    """
    defaults = dict(
        temperature=0.7,
        top_p=1.0,
        sonnet_model_version="claude-sonnet-4-20250514",
        haiku_model_version="claude-haiku-4-20250414",
        compression_frequency=5,
        recent_history_window=3,
        max_context_tokens=4096,
        turn_structure="sequential",
        agent_action_order=["job_seeker", "recruiter", "hiring_manager"],
        reflection_frequency=3,
        interview_turn_floor=2,
        interview_turn_ceiling=6,
        market_condition="balanced",
        ghost_job_percentage=0.1,
        rejection_specificity="moderate",
        new_postings_per_round=2,
        posting_expiry_rounds=10,
        num_seekers=20,
        num_companies=5,
        num_postings=15,
        total_rounds=30,
    )
    defaults.update(overrides)
    return RunConfig(**defaults)


class TestInterviewTurnsValidator:
    """Tests for the validate_interview_turns model validator."""

    def test_floor_exceeds_ceiling_raises(self):
        """Raises when floor is greater than ceiling."""
        with pytest.raises(ValidationError, match="interview_turn_floor"):
            _make_config(interview_turn_floor=8, interview_turn_ceiling=4)

    def test_floor_equals_ceiling_passes(self):
        """Boundary case: equal values are valid."""
        config = _make_config(interview_turn_floor=4, interview_turn_ceiling=4)
        assert config.interview_turn_floor == config.interview_turn_ceiling

    def test_floor_below_ceiling_passes(self):
        """Normal case: floor < ceiling is valid."""
        config = _make_config(interview_turn_floor=2, interview_turn_ceiling=6)
        assert config.interview_turn_floor < config.interview_turn_ceiling