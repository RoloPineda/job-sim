"""Shared value objects used across agent schemas."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Education(BaseModel):
    """A single educational credential.

    Attributes:
        school: Name of the institution.
        degree: Degree earned or expected (e.g., BS, MS, PhD).
        year: Graduation year or expected graduation year.
    """

    model_config = ConfigDict(frozen=True)

    school: str
    degree: str
    year: int


class WorkEntry(BaseModel):
    """A single entry in a jobseeker's work history.

    Attributes:
        company: Name of the employer.
        title: Job title held.
        start_year: Year the role began.
        start_month: Month the role began (1-12).
        end_year: Year the role ended, or None if current.
        end_month: Month the role ended (1-12), or None if current.
        bullets: Accomplishment descriptions used for resume building.
    """

    model_config = ConfigDict(frozen=True)

    company: str
    title: str
    start_year: int
    start_month: int = Field(ge=1, le=12)
    end_year: int | None = None
    end_month: int | None = Field(default=None, ge=1, le=12)
    bullets: tuple[str, ...]

    @model_validator(mode="after")
    def validate_end_date(self) -> "WorkEntry":
        """Ensure end_year and end_month are both set or both None."""
        if (self.end_year is None) != (self.end_month is None):
            raise ValueError("end_year and end_month must both be set or both be None")
        return self
