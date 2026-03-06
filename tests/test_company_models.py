"""Tests for company and job posting schemas."""

import pytest
from pydantic import ValidationError

from tests.helpers import make_company


class TestDelayVarianceValidator:
    """Tests for the validate_delay_variance model validator."""

    def test_variance_equals_delay_raises(self):
        """Raises when variance is equal to base delay."""
        with pytest.raises(ValidationError, match="response_delay_variance"):
            make_company(base_response_delay=3, response_delay_variance=3)

    def test_variance_exceeds_delay_raises(self):
        """Raises when variance exceeds base delay."""
        with pytest.raises(ValidationError, match="response_delay_variance"):
            make_company(base_response_delay=3, response_delay_variance=5)

    def test_variance_one_below_delay_passes(self):
        """Boundary case: variance exactly one less than base delay."""
        profile = make_company(base_response_delay=3, response_delay_variance=2)
        assert profile.response_delay_variance < profile.base_response_delay

    def test_valid_delay_config(self):
        """Normal case: small variance relative to base delay."""
        profile = make_company(base_response_delay=5, response_delay_variance=1)
        assert profile.base_response_delay == 5
        assert profile.response_delay_variance == 1
