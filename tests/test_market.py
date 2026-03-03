"""Tests for market models."""

import pytest
from pydantic import ValidationError

from src.models.market import CompanyProfile, PostingConfig


class TestCompanyProfile:
    """Tests for CompanyProfile model."""

    @pytest.fixture()
    def company_data(self) -> dict:
        return {
            "id": "c1",
            "name": "Acme Corp",
            "industry": "Technology",
            "size": "mid",
            "growth_stage": "scaling",
            "culture_description": "Fast-paced and collaborative",
            "budget_flexibility": "moderate",
            "responsiveness_pattern": "fast",
            "base_response_delay": 1,
            "response_delay_variance": 1,
        }

    def test_valid_company(self, company_data: dict) -> None:
        company = CompanyProfile(**company_data)
        assert company.name == "Acme Corp"
        assert company.size == "mid"
        assert company.growth_stage == "scaling"

    def test_invalid_size_rejected(self, company_data: dict) -> None:
        company_data["size"] = "huge"
        with pytest.raises(ValidationError):
            CompanyProfile(**company_data)

    def test_invalid_growth_stage_rejected(self, company_data: dict) -> None:
        company_data["growth_stage"] = "declining"
        with pytest.raises(ValidationError):
            CompanyProfile(**company_data)

    def test_invalid_budget_flexibility_rejected(self, company_data: dict) -> None:
        company_data["budget_flexibility"] = "unlimited"
        with pytest.raises(ValidationError):
            CompanyProfile(**company_data)

    def test_invalid_responsiveness_rejected(self, company_data: dict) -> None:
        company_data["responsiveness_pattern"] = "instant"
        with pytest.raises(ValidationError):
            CompanyProfile(**company_data)

    def test_missing_required_field(self, company_data: dict) -> None:
        del company_data["name"]
        with pytest.raises(ValidationError):
            CompanyProfile(**company_data)

    def test_serialization_roundtrip(self, company_data: dict) -> None:
        company = CompanyProfile(**company_data)
        data = company.model_dump()
        restored = CompanyProfile(**data)
        assert restored == company

    def test_wrong_type_for_int_field(self, company_data: dict) -> None:
        company_data["base_response_delay"] = "fast"
        with pytest.raises(ValidationError):
            CompanyProfile(**company_data)


class TestPostingConfig:
    """Tests for PostingConfig model."""

    @pytest.fixture()
    def posting_data(self) -> dict:
        return {
            "id": "p1",
            "company_id": "c1",
            "title": "Software Engineer",
            "department": "Engineering",
            "description": "Build and maintain backend services",
            "requirements": ["Python", "SQL", "REST APIs"],
            "location": "San Francisco, CA",
            "remote": True,
            "seniority": "mid",
            "posted_round": 1,
        }

    def test_valid_posting(self, posting_data: dict) -> None:
        posting = PostingConfig(**posting_data)
        assert posting.title == "Software Engineer"
        assert posting.requirements == ["Python", "SQL", "REST APIs"]
        assert posting.remote is True

    def test_defaults(self, posting_data: dict) -> None:
        posting = PostingConfig(**posting_data)
        assert posting.status == "open"
        assert posting.is_ghost is False
        assert posting.is_underpaid is False
        assert posting.is_realistic is True
        assert posting.actual_budget is None
        assert posting.salary_range_low is None
        assert posting.salary_range_high is None
        assert posting.expiry_round is None

    def test_hidden_attributes(self, posting_data: dict) -> None:
        posting_data["is_ghost"] = True
        posting_data["is_underpaid"] = True
        posting_data["actual_budget"] = 150000
        posting = PostingConfig(**posting_data)
        assert posting.is_ghost is True
        assert posting.is_underpaid is True
        assert posting.actual_budget == 150000

    def test_optional_salary_range(self, posting_data: dict) -> None:
        posting_data["salary_range_low"] = 120000
        posting_data["salary_range_high"] = 180000
        posting = PostingConfig(**posting_data)
        assert posting.salary_range_low == 120000
        assert posting.salary_range_high == 180000

    def test_invalid_seniority_rejected(self, posting_data: dict) -> None:
        posting_data["seniority"] = "principal"
        with pytest.raises(ValidationError):
            PostingConfig(**posting_data)

    def test_invalid_status_rejected(self, posting_data: dict) -> None:
        posting_data["status"] = "archived"
        with pytest.raises(ValidationError):
            PostingConfig(**posting_data)

    def test_serialization_roundtrip(self, posting_data: dict) -> None:
        posting = PostingConfig(**posting_data)
        data = posting.model_dump()
        restored = PostingConfig(**data)
        assert restored == posting

    def test_empty_requirements_list(self, posting_data: dict) -> None:
        posting_data["requirements"] = []
        posting = PostingConfig(**posting_data)
        assert posting.requirements == []

    def test_non_bool_string_coerced_to_bool(self, posting_data: dict) -> None:
        """Pydantic coerces truthy strings like 'yes' to True."""
        posting_data["remote"] = "yes"
        posting = PostingConfig(**posting_data)
        assert posting.remote is True

    def test_missing_required_field(self, posting_data: dict) -> None:
        del posting_data["title"]
        with pytest.raises(ValidationError):
            PostingConfig(**posting_data)

    def test_json_roundtrip(self, posting_data: dict) -> None:
        """Validate JSON serialization/deserialization preserves all fields."""
        posting_data["is_ghost"] = True
        posting_data["actual_budget"] = 200000
        posting = PostingConfig(**posting_data)
        json_str = posting.model_dump_json()
        restored = PostingConfig.model_validate_json(json_str)
        assert restored == posting
        assert restored.is_ghost is True
        assert restored.actual_budget == 200000
