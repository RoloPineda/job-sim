"""Agent profile schemas.

All profiles are frozen. Mutable per-round data lives in
schemas.states instead.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.shared import Education, WorkEntry
from schemas.types import AgentType


class AgentProfile(BaseModel):
    """Stable identity and disposition for a simulation agent.

    These attributes are immutable since they don't change over the
    course of a job search. All subclasses inherit frozen=True.

    Attributes:
        id: Unique agent identifier.
        agent_type: The role this agent plays in the simulation.
        name: Display name.
        disposition: Personality traits that shape decision-making.
        backstory: Background narrative seeded at creation, never modified.
        location: Where the agent is based.
    """

    model_config = ConfigDict(frozen=True)
    id: str
    agent_type: AgentType
    name: str
    disposition: str
    backstory: str
    location: str


class JobSeekerProfile(AgentProfile):
    """A jobseeker's immutable profile including skills and traits.

    The agent builds its own resume from perceived_skills, work_history,
    education, and projects. actual_skills is hidden from the agent and
    used only for post-simulation analysis.

    Mutable fields (savings, burn_rate, target preferences) live on
    SeekerState, not here.

    Attributes:
        education_history: Academic background (e.g., HS, BS, MS, PhD).
        actual_skills: Ground truth skills, never included in agent prompts.
        experience_years: Total years of professional experience.
        work_history: Past roles with accomplishments for resume building.
        perceived_skills: Skills the agent believes it has.
        self_awareness: How accurately the agent assesses its own abilities.
        communication_ability: How effectively the agent communicates.
    """

    education_history: list[Education]
    actual_skills: list[str]
    work_history: list[WorkEntry] = Field(min_length=0)
    experience_years: int = Field(ge=0)

    perceived_skills: list[str]
    self_awareness: Literal["accurate", "overconfident", "underconfident"]
    communication_ability: Literal["strong", "average", "weak"]


class RecruiterProfile(AgentProfile):
    """Profile for a recruiter agent.

    Represents a recruiter's company assignment, scope of responsibilities,
    and capability level. The recruiter serves as the middleman between
    jobseekers and hiring managers, screening candidates and managing
    communication between both sides.

    Attributes:
        company_id: The company this recruiter works for.
        assigned_posting_ids: Job postings this recruiter is responsible for.
        hiring_manager_ids: Hiring managers this recruiter works with.
        experience_level: General recruiter competence level.
        current_workload: Number of open roles currently being managed.
    """

    company_id: str
    assigned_posting_ids: list[str]
    hiring_manager_ids: list[str]
    experience_level: Literal["junior", "mid", "senior"]
    current_workload: int = Field(ge=0)


class HiringManagerProfile(AgentProfile):
    """Profile for a hiring manager agent.

    Represents a hiring manager's team context, interview style, and
    decision-making tendencies. The hiring manager is the final
    decision-maker on candidates, setting the bar and deciding on offers.

    Attributes:
        company_id: The company this hiring manager belongs to.
        team_size: Current size of the hiring manager's team.
        team_situation: State of the team affecting hiring urgency.
        management_style: How the manager interacts with candidates
            and recruiters.
        technical_bar: Freeform description of what the manager values
            in candidates.
        interview_capacity_per_round: Maximum interviews the manager
            can conduct per round.
        past_hiring_description: Context about previous hires and
            preferences that may reveal implicit biases.
        feedback_clarity: How clearly the manager communicates
            expectations to recruiters.
    """

    company_id: str
    team_size: int = Field(ge=0)
    team_situation: Literal["understaffed", "stable", "growing", "rebuilding"]
    management_style: Literal["detailed_feedback", "vague", "responsive", "slow", "micromanager"]
    technical_bar: str
    interview_capacity_per_round: int = Field(ge=0)
    past_hiring_description: str
    feedback_clarity: Literal["clear", "vague", "contradictory"]
