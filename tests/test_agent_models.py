"""Tests for agent profile and state schemas."""

import pytest
from pydantic import ValidationError

from tests.helpers import (
    make_education,
    make_job_seeker,
    make_seeker_state,
    make_work_entry,
)


@pytest.fixture()
def education():
    """Return a minimal Education instance."""
    return make_education()


@pytest.fixture()
def work_entry():
    """Return a minimal WorkEntry instance."""
    return make_work_entry()


class TestCompRangeValidator:
    """Tests for the validate_comp_range model validator on JobSeekerState."""

    def test_low_exceeds_high_raises(self):
        """Raises ValueError when target_comp_low > target_comp_high."""
        with pytest.raises(ValidationError, match="target_comp_low"):
            make_seeker_state(
                target_comp_low=150_000,
                target_comp_high=100_000,
            )

    def test_low_equals_high_passes(self):
        """Boundary case: equal values are valid."""
        state = make_seeker_state(
            target_comp_low=100_000,
            target_comp_high=100_000,
        )
        assert state.target_comp_low == state.target_comp_high

    def test_low_below_high_passes(self):
        """Normal case: low < high is valid."""
        state = make_seeker_state(target_comp_low=80_000, target_comp_high=120_000)
        assert state.target_comp_low < state.target_comp_high


class TestModuleWiring:
    """Verify that schemas referencing forward-declared types construct properly."""

    def test_job_seeker_construction(self, education, work_entry):
        """JobSeekerProfile resolves Education and WorkEntry references."""
        profile = make_job_seeker(education, work_entry)
        assert profile.education_history[0].school == "State University"
        assert profile.work_history[0].company == "Acme Corp"

    def test_seeker_state_construction(self):
        """JobSeekerState constructs with default mutable fields."""
        state = make_seeker_state()
        assert state.savings == 10_000
        assert state.burn_rate == 2_000
        assert state.current_resume is None
        assert state.total_applications == 0
