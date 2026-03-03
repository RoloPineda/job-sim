"""Market models for companies and job postings."""

from typing import Literal

from pydantic import BaseModel, Field


class CompanyProfile(BaseModel):
    """A company's identity and behavioral tendencies.

    Stable foundation that influences how the company's recruiter and hiring
    manager agents behave. Not modified during a simulation run.
    """

    id: str
    name: str
    industry: str
    size: Literal["startup", "mid", "enterprise"]
    growth_stage: Literal["early", "scaling", "mature"]
    culture_description: str
    budget_flexibility: Literal["rigid", "moderate", "flexible"]
    responsiveness_pattern: Literal["fast", "slow", "unpredictable", "ghosts"]
    base_response_delay: int = Field(description="Rounds before typical response")
    response_delay_variance: int = Field(description="Randomness added to delay")


class PostingConfig(BaseModel):
    """A single job posting on the board.

    Includes hidden attributes that agents cannot see directly but that
    affect simulation behavior (e.g. ghost jobs, underpaid roles).
    """

    id: str
    company_id: str
    title: str
    department: str
    description: str
    requirements: list[str]
    salary_range_low: int | None = None
    salary_range_high: int | None = None
    location: str
    remote: bool
    seniority: Literal["junior", "mid", "senior", "lead", "staff"]
    posted_round: int
    expiry_round: int | None = None
    status: Literal["open", "closed", "filled", "expired"] = "open"

    # Hidden attributes — stripped before agents see them
    is_ghost: bool = False
    is_underpaid: bool = False
    is_realistic: bool = True
    actual_budget: int | None = None
