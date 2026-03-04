"""Tests for agent profile and state models."""

import pytest
from pydantic import ValidationError

from src.models.agents import (
    Education,
    JobSeekerProfile,
    WorkEntry,
)

@pytest.fixture()
def education():
    """Return a minimal Education instance."""
    return Education(school="State University", degree="BS", year=2020)


@pytest.fixture()
def work_entry():
    """Return a minimal WorkEntry instance."""
    return WorkEntry(
        company="Acme Corp",
        title="Engineer",
        start_year=2020,
        start_month=6,
        end_year=2022,
        end_month=5,
        bullets=("Built things.",),
    )


def _make_job_seeker(education, work_entry, **overrides):
    """Build a valid JobSeekerProfile, merging any field overrides.

    Args:
        education: An Education instance for the education_history field.
        work_entry: A WorkEntry instance for the work_history field.
        **overrides: Any JobSeekerProfile fields to override.

    Returns:
        A fully constructed JobSeekerProfile.
    """
    defaults = dict(
        id="js-1",
        agent_type="job_seeker",
        name="Alice",
        disposition="motivated",
        backstory="Grew up tinkering with computers.",
        location="Austin, TX",
        education_history=[education],
        actual_skills=["python", "sql"],
        perceived_skills=["python", "sql", "leadership"],
        work_history=[work_entry],
        experience_years=3,
        self_awareness="accurate",
        communication_ability="strong",
        target_roles=["Software Engineer"],
        target_seniority="mid",
        target_comp_low=80_000,
        target_comp_high=120_000,
        location_flexibility="moderate",
        remote_preference="hybrid",
        savings=10_000,
        burn_rate=2_000,
    )
    defaults.update(overrides)
    return JobSeekerProfile(**defaults)


class TestCompRangeValidator:
    """Tests for the validate_comp_range model validator."""

    def test_low_exceeds_high_raises(self, education, work_entry):
        """Raises ValueError when target_comp_low > target_comp_high."""
        with pytest.raises(ValidationError, match="target_comp_low"):
            _make_job_seeker(
                education,
                work_entry,
                target_comp_low=150_000,
                target_comp_high=100_000,
            )

    def test_low_equals_high_passes(self, education, work_entry):
        """Boundary case: equal values are valid."""
        profile = _make_job_seeker(
            education,
            work_entry,
            target_comp_low=100_000,
            target_comp_high=100_000,
        )
        assert profile.target_comp_low == profile.target_comp_high

    def test_low_below_high_passes(self, education, work_entry):
        """Normal case: low < high is valid."""
        profile = _make_job_seeker(
            education, work_entry, target_comp_low=80_000, target_comp_high=120_000
        )
        assert profile.target_comp_low < profile.target_comp_high


class TestModuleWiring:
    """Verify that models referencing forward-declared types construct properly."""

    def test_job_seeker_construction(self, education, work_entry):
        """JobSeekerProfile resolves Education and WorkEntry references."""
        profile = _make_job_seeker(education, work_entry)
        assert profile.education_history[0].school == "State University"
        assert profile.work_history[0].company == "Acme Corp"
