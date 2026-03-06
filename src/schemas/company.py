"""Company and job posting schemas"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CompanyProfile(BaseModel):
    """Profile representing a company's identity and hiring behavior.

    Immutable for the duration of a simulation. Companies are unlikely
    to change their hiring behaviors during a period of 3-6 months
    unless major events happen.

    Attributes:
        id: Unique company identifier.
        name: Company name.
        industry: Sector the company operates in.
        size: Scale of the company as a behavioral signal.
        growth_stage: Where the company is in its lifecycle.
        culture_description: Freeform text describing company culture
            and values, fed into recruiter and HM prompts.
        budget_flexibility: How much room the company has to negotiate
            on compensation.
        responsiveness_pattern: How the company typically responds to
            candidates.
        base_response_delay: Number of rounds before the company
            typically responds. Fixed trait set at seeding. Minimum of
            1 since a company cannot respond in zero rounds. The actual
            delay for any specific interaction is computed at runtime
            by the engine using this value combined with
            response_delay_variance.
        response_delay_variance: Range of randomness added to
            base_response_delay. At runtime, the engine computes the
            actual delay as base_response_delay plus or minus up to
            this value, clamped to at least 1. This is not randomized
            at seeding. It is a fixed property that tells the engine
            how predictable this company's response times are. Must be
            less than base_response_delay to avoid negative delays.
        rejection_specificity: How much detail companies give when
            rejecting candidates.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    industry: Literal[
        "technology",
        "finance",
        "healthcare",
        "retail",
        "media",
        "education",
        "manufacturing",
        "consulting",
    ]
    size: Literal["startup", "mid", "enterprise"]
    growth_stage: Literal["early", "scaling", "mature"]
    culture_description: str
    budget_flexibility: Literal["rigid", "moderate", "flexible"]
    responsiveness_pattern: Literal["fast", "slow", "unpredictable", "ghosts"]
    base_response_delay: int = Field(ge=1)
    response_delay_variance: int = Field(ge=0)
    rejection_specificity: Literal["high", "moderate", "low"]

    @model_validator(mode="after")
    def validate_delay_variance(self) -> "CompanyProfile":
        """Ensure response_delay_variance is less than base_response_delay."""
        if self.response_delay_variance >= self.base_response_delay:
            raise ValueError(
                f"response_delay_variance ({self.response_delay_variance}) "
                f"must be less than base_response_delay "
                f"({self.base_response_delay})"
            )
        return self


class JobPosting(BaseModel):
    """A job listing on the simulation's job board.

    Contains both visible attributes that jobseekers can see when
    browsing and hidden attributes that only the simulation engine
    uses to determine outcomes.

    Attributes:
        id: Unique posting identifier.
        company_id: Company that owns this posting.
        hiring_manager_id: Hiring manager responsible for this role.
        title: Job title as displayed to seekers.
        department: Team or org the role sits in.
        description: Freeform job description visible to seekers.
        requirements: Stated requirements seekers evaluate themselves
            against.
        salary_range_low: Bottom of posted salary range in yearly
            dollars, or None if undisclosed.
        salary_range_high: Top of posted salary range in yearly
            dollars, or None if undisclosed.
        location: Where the role is based.
        remote: Whether the role is remote.
        seniority: Level of the role.
        round_posted: Simulation round when the posting went live.
            Round timescale is defined in RunConfig.
        round_expires: Simulation round when the posting comes off
            the board, or None if open-ended.
        status: Current state of the posting. Mutable as it
            progresses through its lifecycle.
        is_ghost: Hidden flag. If true, the posting accepts
            applications but never advances anyone.
        actual_budget: Hidden field. Real budget for the role which
            may differ from the posted range. Used to evaluate
            offers and negotiations.
    """

    id: str
    company_id: str
    hiring_manager_id: str
    title: str
    department: str
    description: str
    requirements: list[str]
    salary_range_low: int | None = None
    salary_range_high: int | None = None
    location: str
    remote: bool
    seniority: Literal["junior", "mid", "senior", "lead", "staff"]
    round_posted: int = Field(ge=0)
    round_expires: int | None = None
    status: Literal["open", "closed", "filled", "expired"] = "open"
    is_ghost: bool = False
    actual_budget: int | None = None
