"""Tests for simulation run configuration schemas."""

import pytest
from pydantic import ValidationError

from tests.helpers import make_config


class TestInterviewTurnsValidator:
    """Tests for the validate_interview_turns model validator."""

    def test_floor_exceeds_ceiling_raises(self):
        """Raises when floor is greater than ceiling."""
        with pytest.raises(ValidationError, match="interview_turn_floor"):
            make_config(interview_turn_floor=8, interview_turn_ceiling=4)

    def test_floor_equals_ceiling_passes(self):
        """Boundary case: equal values are valid."""
        config = make_config(interview_turn_floor=4, interview_turn_ceiling=4)
        assert config.interview_turn_floor == config.interview_turn_ceiling

    def test_floor_below_ceiling_passes(self):
        """Normal case: floor < ceiling is valid."""
        config = make_config(interview_turn_floor=2, interview_turn_ceiling=6)
        assert config.interview_turn_floor < config.interview_turn_ceiling
