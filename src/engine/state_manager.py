"""Data access layer bridging ORM models and Pydantic agent schemas.

Handles hydration (ORM to Pydantic for agent construction), persistence
(Pydantic side effects back to ORM), and state serialization. The runner
calls into this module but manages transaction boundaries itself.
"""

import logging
import uuid as uuid_mod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.agents import Agent, HiringManager, JobSeeker, Recruiter
from models.company import Company
from models.company import JobPosting as JobPostingModel
from models.observability import Event as EventModel
from models.observability import Reflection, StateSnapshot
from models.records import (
    Application as ApplicationModel,
)
from models.records import (
    RecruiterHMMessage as MessageModel,
)
from models.records import (
    ResumeVersion as ResumeVersionModel,
)
from schemas.company import JobPosting
from schemas.config import RunConfig
from schemas.profiles import (
    HiringManagerProfile,
    JobSeekerProfile,
    RecruiterProfile,
)
from schemas.records import (
    ApplicationRecord,
    EventEntry,
    RecruiterHMMessage,
    ResumeVersion,
)
from schemas.shared import Education, WorkEntry
from schemas.states import (
    AgentState,
    HiringManagerState,
    JobSeekerState,
    RecruiterState,
)
from schemas.types import (
    AgentType,
    ApplicationStatus,
    CommunicationAbility,
    ExperienceLevel,
    FeedbackClarity,
    LocationFlexibility,
    ManagementStyle,
    MessageType,
    PostingStatus,
    RemotePreference,
    SelfAwareness,
    Seniority,
    TeamSituation,
)

logger = logging.getLogger(__name__)


@dataclass
class PendingInterview:
    """An interview that needs to be conducted this round.

    Populated by find_pending_interviews() from applications that
    have been advanced but don't yet have an Interview record.

    Attributes:
        application_id: The advanced application's ID.
        job_seeker_id: The candidate's agent ID.
        posting_id: The posting being interviewed for.
        interviewer_id: The hiring manager's agent ID.
        interviewer_type: Always "hiring_manager" for now. Will
            support "recruiter" when recruiter screens are added.
        round_scheduled: The round the application was advanced.
    """

    application_id: str
    job_seeker_id: str
    posting_id: str
    interviewer_id: str
    interviewer_type: str
    round_scheduled: int


@dataclass
class JobSeekerBundle:
    """All data needed to construct a JobSeekerAgent."""

    profile: JobSeekerProfile
    state: JobSeekerState


@dataclass
class RecruiterBundle:
    """All data needed to construct a RecruiterAgent."""

    profile: RecruiterProfile
    state: RecruiterState
    postings: list[JobPosting]
    applications: list[ApplicationRecord]
    hm_messages: list[RecruiterHMMessage]
    job_seeker_info: dict[str, dict[str, str]]


@dataclass
class HiringManagerBundle:
    """All data needed to construct a HiringManagerAgent."""

    profile: HiringManagerProfile
    state: HiringManagerState
    postings: list[JobPosting]
    applications: list[ApplicationRecord]
    recruiter_messages: list[RecruiterHMMessage]
    job_seeker_info: dict[str, dict[str, str]]
    recruiter_info: dict[str, str]


@dataclass
class BackgroundOutcome:
    """A scheduled response from a background company."""

    application_id: str
    job_seeker_id: str
    posting_id: str
    posting_title: str
    round_due: int
    outcome: str


class StateManager:
    """Bridges the ORM layer and Pydantic agent schemas.

    Provides methods for loading agent data bundles from the database
    and persisting side effects after agent turns. Does not manage
    transaction boundaries; the caller is responsible for committing
    or rolling back the session.

    Args:
        session: SQLAlchemy async session.
        run_id: The simulation run to scope all queries to.
        config: Simulation-wide parameters.
    """

    def __init__(
        self,
        session: AsyncSession,
        run_id: uuid_mod.UUID,
        config: RunConfig,
    ) -> None:
        self._session = session
        self._run_id = run_id
        self._config = config
        self._agent_company_ids: set[str] | None = None

    async def load_job_seeker_bundles(self, round_number: int) -> list[JobSeekerBundle]:
        """Loads all jobseeker agents with their data for a round.

        On round 1, state is hydrated from ORM columns. On subsequent
        rounds, state is deserialized from the Agent.state JSONB column.

        Args:
            round_number: The current simulation round.

        Returns:
            A JobSeekerBundle per seeker in this run.
        """
        stmt = select(JobSeeker).where(JobSeeker.run_id == self._run_id)
        result = await self._session.execute(stmt)
        job_seekers = result.scalars().all()

        bundles = []
        for orm in job_seekers:
            profile = self._hydrate_job_seeker_profile(orm)
            state = self._hydrate_job_seeker_state(orm, round_number)
            bundles.append(
                JobSeekerBundle(
                    profile=profile,
                    state=state,
                )
            )
        return bundles

    async def load_open_postings(self) -> list[JobPosting]:
        """Loads all open postings for the run.

        Returns:
            All open job postings in this simulation run.
        """
        return await self._load_open_postings()

    async def load_recruiter_bundles(self, round_number: int) -> list[RecruiterBundle]:
        """Loads all recruiter agents with their data for a round.

        Args:
            round_number: The current simulation round.

        Returns:
            A RecruiterBundle per recruiter in this run.
        """
        stmt = (
            select(Recruiter)
            .where(Recruiter.run_id == self._run_id)
            .options(selectinload(Recruiter.assigned_postings))
        )
        result = await self._session.execute(stmt)
        recruiters = result.scalars().all()

        bundles = []
        for orm in recruiters:
            profile = self._hydrate_recruiter_profile(orm)
            state = self._hydrate_recruiter_state(orm, round_number)

            posting_ids = [p.id for p in orm.assigned_postings]
            postings = [await self._orm_posting_to_pydantic(p) for p in orm.assigned_postings]

            applications = await self._load_applications_for_postings(posting_ids)
            hm_messages = await self._load_messages_for_agent(orm.id)

            job_seeker_ids = {a.job_seeker_id for a in applications}
            job_seeker_info = await self._build_job_seeker_info(job_seeker_ids)

            bundles.append(
                RecruiterBundle(
                    profile=profile,
                    state=state,
                    postings=postings,
                    applications=applications,
                    hm_messages=hm_messages,
                    job_seeker_info=job_seeker_info,
                )
            )
        return bundles

    async def load_hm_bundles(self, round_number: int) -> list[HiringManagerBundle]:
        """Loads all hiring manager agents with their data for a round.

        Args:
            round_number: The current simulation round.

        Returns:
            A HiringManagerBundle per HM in this run.
        """
        stmt = (
            select(HiringManager)
            .where(HiringManager.run_id == self._run_id)
            .options(selectinload(HiringManager.managed_postings))
        )
        result = await self._session.execute(stmt)
        hms = result.scalars().all()

        bundles = []
        for orm in hms:
            profile = self._hydrate_hm_profile(orm)
            state = self._hydrate_hm_state(orm, round_number)

            postings = [await self._orm_posting_to_pydantic(p) for p in orm.managed_postings]

            applications = await self._load_forwarded_applications(
                [p.id for p in orm.managed_postings]
            )
            messages = await self._load_messages_for_agent(orm.id)

            job_seeker_ids = {a.job_seeker_id for a in applications}
            job_seeker_info = await self._build_job_seeker_info(job_seeker_ids)
            recruiter_info = await self._build_recruiter_info(messages)

            bundles.append(
                HiringManagerBundle(
                    profile=profile,
                    state=state,
                    postings=postings,
                    applications=applications,
                    recruiter_messages=messages,
                    job_seeker_info=job_seeker_info,
                    recruiter_info=recruiter_info,
                )
            )
        return bundles

    async def persist_job_seeker_results(
        self,
        bundles: list[JobSeekerBundle],
        resume_versions: list[ResumeVersion],
        applications: list[ApplicationRecord],
        round_number: int,
    ) -> list[ApplicationRecord]:
        """Persists jobseeker side effects and updated state.

        Saves new resume versions and applications, fills in
        recruiter_id on applications to agent-backed companies,
        and writes the updated state to the Agent JSONB column.

        Args:
            bundles: The jobseeker bundles used this round.
            resume_versions: New resume versions produced.
            applications: New applications submitted.
            round_number: Current round for state update.

        Returns:
            Applications with recruiter_id populated where applicable.
        """
        await self._persist_resume_versions(resume_versions)
        await self._route_applications_to_recruiters(applications)
        await self._persist_applications(applications)

        for bundle in bundles:
            await self._save_agent_state(bundle.profile.id, bundle.state)

        return applications

    async def _persist_resume_versions(self, resume_versions: list[ResumeVersion]) -> None:
        """Writes new resume versions to the database.

        Args:
            resume_versions: Resume versions to persist.
        """
        for rv in resume_versions:
            self._session.add(
                ResumeVersionModel(
                    id=self._to_uuid(rv.id),
                    run_id=self._run_id,
                    job_seeker_id=self._to_uuid(rv.job_seeker_id),
                    round_created=rv.round_created,
                    full_text=rv.full_text,
                    trigger=rv.trigger,
                    target_posting_id=(
                        self._to_uuid(rv.target_posting_id) if rv.target_posting_id else None
                    ),
                    state_summary_at_creation=rv.state_summary_at_creation,
                )
            )

    async def _route_applications_to_recruiters(
        self, applications: list[ApplicationRecord]
    ) -> None:
        """Fills in recruiter_id on applications to agent-backed companies.

        Applications to background companies keep recruiter_id as None.

        Args:
            applications: Applications to route, modified in place.
        """
        agent_company_ids = await self._get_agent_company_ids()
        posting_recruiter_map = await self._build_posting_recruiter_map()

        for app in applications:
            posting_company = await self._get_posting_company_id(app.posting_id)
            if not posting_company:
                continue
            if str(posting_company) not in agent_company_ids:
                continue
            recruiter_id = posting_recruiter_map.get(app.posting_id)
            if recruiter_id:
                app.recruiter_id = str(recruiter_id)

    async def _persist_applications(self, applications: list[ApplicationRecord]) -> None:
        """Writes applications to the database.

        Only persists applications that have a recruiter_id assigned,
        since background company applications are tracked in agent
        state only.

        Args:
            applications: Applications to persist.
        """
        for app in applications:
            if not app.recruiter_id:
                continue
            self._session.add(
                ApplicationModel(
                    id=self._to_uuid(app.id),
                    run_id=self._run_id,
                    job_seeker_id=self._to_uuid(app.job_seeker_id),
                    posting_id=self._to_uuid(app.posting_id),
                    recruiter_id=self._to_uuid(app.recruiter_id),
                    resume_version_id=self._to_uuid(app.resume_version_id),
                    round_submitted=app.round_submitted,
                    status=app.status,
                )
            )

    async def persist_recruiter_results(
        self,
        bundles: list[RecruiterBundle],
        hm_messages: list[RecruiterHMMessage],
        events: list[EventEntry],
        modified_applications: list[ApplicationRecord],
    ) -> None:
        """Persists recruiter side effects and updated state.

        Args:
            bundles: The recruiter bundles used this round.
            hm_messages: Messages sent to hiring managers.
            events: Status notifications created for jobseekers.
            modified_applications: Applications whose status changed.
        """
        for msg in hm_messages:
            self._session.add(
                MessageModel(
                    id=self._to_uuid(msg.id),
                    run_id=self._run_id,
                    sender_id=self._to_uuid(msg.sender_id),
                    receiver_id=self._to_uuid(msg.receiver_id),
                    round_sent=msg.round_sent,
                    content=msg.content,
                    message_type=msg.message_type,
                    posting_id=self._to_uuid(msg.posting_id),
                    related_application_id=(
                        self._to_uuid(msg.related_application_id)
                        if msg.related_application_id
                        else None
                    ),
                )
            )

        await self.persist_events(events)
        await self._update_application_statuses(modified_applications)

        for bundle in bundles:
            await self._save_agent_state(bundle.profile.id, bundle.state)

    async def persist_hm_results(
        self,
        bundles: list[HiringManagerBundle],
        hm_messages: list[RecruiterHMMessage],
        events: list[EventEntry],
        modified_applications: list[ApplicationRecord],
    ) -> None:
        """Persists hiring manager side effects and updated state.

        Args:
            bundles: The HM bundles used this round.
            hm_messages: Feedback messages sent to recruiters.
            events: Rejection notifications created for jobseekers.
            modified_applications: Applications whose status changed.
        """
        for msg in hm_messages:
            self._session.add(
                MessageModel(
                    id=self._to_uuid(msg.id),
                    run_id=self._run_id,
                    sender_id=self._to_uuid(msg.sender_id),
                    receiver_id=self._to_uuid(msg.receiver_id),
                    round_sent=msg.round_sent,
                    content=msg.content,
                    message_type=msg.message_type,
                    posting_id=self._to_uuid(msg.posting_id),
                    related_application_id=(
                        self._to_uuid(msg.related_application_id)
                        if msg.related_application_id
                        else None
                    ),
                )
            )

        await self.persist_events(events)
        await self._update_application_statuses(modified_applications)

        for bundle in bundles:
            await self._save_agent_state(bundle.profile.id, bundle.state)

    async def write_snapshots(self, round_number: int) -> None:
        """Writes a state snapshot for every agent in the run.

        Args:
            round_number: The current simulation round.
        """
        stmt = select(Agent).where(Agent.run_id == self._run_id)
        result = await self._session.execute(stmt)
        agents = result.scalars().all()

        for agent in agents:
            self._session.add(
                StateSnapshot(
                    id=uuid_mod.uuid4(),
                    run_id=self._run_id,
                    agent_id=agent.id,
                    agent_type=agent.agent_type,
                    round_number=round_number,
                    state_json=agent.state or {},
                    created_at=datetime.now(timezone.utc),
                )
            )

    async def save_reflection(
        self,
        agent_id: str,
        agent_type: str,
        round_number: int,
        prompt_used: str,
        response: str,
        context_summary: str,
    ) -> None:
        """Persists an agent reflection.

        Args:
            agent_id: The reflecting agent's ID.
            agent_type: The agent's type string.
            round_number: Round the reflection was generated.
            prompt_used: The full reflection prompt.
            response: The agent's response text.
            context_summary: State summary at reflection time.
        """
        self._session.add(
            Reflection(
                id=uuid_mod.uuid4(),
                run_id=self._run_id,
                agent_id=self._to_uuid(agent_id),
                agent_type=agent_type,
                round_number=round_number,
                prompt_used=prompt_used,
                response=response,
                context_summary=context_summary,
            )
        )

    async def detect_background_applications(
        self, applications: list[ApplicationRecord]
    ) -> list[tuple[ApplicationRecord, str, str]]:
        """Identifies applications to background companies.

        Returns each background application with its company's
        responsiveness_pattern and computed response delay.

        Args:
            applications: Newly submitted applications.

        Returns:
            List of (application, responsiveness_pattern, company_id)
            tuples for background company applications.
        """
        agent_company_ids = await self._get_agent_company_ids()
        background_apps = []

        for app in applications:
            posting_company = await self._get_posting_company_id(app.posting_id)
            if posting_company and str(posting_company) not in agent_company_ids:
                company = await self._load_company(posting_company)
                if company:
                    background_apps.append(
                        (
                            app,
                            company.responsiveness_pattern,
                            str(posting_company),
                        )
                    )

        return background_apps

    async def load_company_response_params(self, company_id: str) -> tuple[int, int]:
        """Loads a company's response delay parameters.

        Args:
            company_id: The company to look up.

        Returns:
            Tuple of (base_response_delay, response_delay_variance).
        """
        company = await self._load_company(self._to_uuid(company_id))
        if not company:
            return (3, 1)
        return company.base_response_delay, company.response_delay_variance

    def _hydrate_job_seeker_profile(self, orm: JobSeeker) -> JobSeekerProfile:
        return JobSeekerProfile(
            id=str(orm.id),
            agent_type=cast(AgentType, orm.agent_type),
            name=orm.name,
            disposition=orm.disposition,
            backstory=orm.backstory,
            location=orm.location,
            education_history=[Education(**e) for e in orm.education_history],
            actual_skills=list(orm.actual_skills),
            work_history=[WorkEntry(**w) for w in orm.work_history],
            experience_years=orm.experience_years,
            perceived_skills=list(orm.perceived_skills),
            self_awareness=cast(SelfAwareness, orm.self_awareness),
            communication_ability=cast(CommunicationAbility, orm.communication_ability),
        )

    def _hydrate_job_seeker_state(self, orm: JobSeeker, round_number: int) -> JobSeekerState:
        if orm.state and round_number > 1:
            state = JobSeekerState.model_validate(orm.state)
            state.round_number = round_number
            return state

        return JobSeekerState(
            round_number=round_number,
            savings=orm.savings,
            burn_rate=orm.burn_rate,
            target_roles=list(orm.target_roles),
            target_seniority=cast(Seniority, orm.target_seniority),
            target_comp_low=orm.target_comp_low,
            target_comp_high=orm.target_comp_high,
            location_flexibility=cast(LocationFlexibility, orm.location_flexibility),
            remote_preference=cast(RemotePreference, orm.remote_preference),
        )

    def _hydrate_recruiter_profile(self, orm: Recruiter) -> RecruiterProfile:
        posting_ids = [str(p.id) for p in orm.assigned_postings]
        hm_ids = list({str(p.hiring_manager_id) for p in orm.assigned_postings})

        return RecruiterProfile(
            id=str(orm.id),
            agent_type=cast(AgentType, orm.agent_type),
            name=orm.name,
            disposition=orm.disposition,
            backstory=orm.backstory,
            location=orm.location,
            company_id=str(orm.company_id),
            assigned_posting_ids=posting_ids,
            hiring_manager_ids=hm_ids,
            experience_level=cast(ExperienceLevel, orm.experience_level),
            current_workload=orm.current_workload,
        )

    def _hydrate_recruiter_state(self, orm: Recruiter, round_number: int) -> RecruiterState:
        if orm.state and round_number > 1:
            state = RecruiterState.model_validate(orm.state)
            state.round_number = round_number
            return state

        return RecruiterState(round_number=round_number)

    def _hydrate_hm_profile(self, orm: HiringManager) -> HiringManagerProfile:
        return HiringManagerProfile(
            id=str(orm.id),
            agent_type=cast(AgentType, orm.agent_type),
            name=orm.name,
            disposition=orm.disposition,
            backstory=orm.backstory,
            location=orm.location,
            company_id=str(orm.company_id),
            team_size=orm.team_size,
            team_situation=cast(TeamSituation, orm.team_situation),
            management_style=cast(ManagementStyle, orm.management_style),
            technical_bar=orm.technical_bar,
            interview_capacity_per_round=orm.interview_capacity_per_round,
            past_hiring_description=orm.past_hiring_description,
            feedback_clarity=cast(FeedbackClarity, orm.feedback_clarity),
        )

    def _hydrate_hm_state(self, orm: HiringManager, round_number: int) -> HiringManagerState:
        if orm.state and round_number > 1:
            state = HiringManagerState.model_validate(orm.state)
            state.round_number = round_number
            return state

        return HiringManagerState(round_number=round_number)

    async def _orm_posting_to_pydantic(self, orm: JobPostingModel) -> JobPosting:
        company_name = await self._get_company_name(orm.company_id)
        return JobPosting(
            id=str(orm.id),
            company_id=str(orm.company_id),
            company_name=company_name,
            hiring_manager_id=str(orm.hiring_manager_id),
            title=orm.title,
            department=orm.department,
            description=orm.description,
            requirements=list(orm.requirements),
            salary_range_low=orm.salary_range_low,
            salary_range_high=orm.salary_range_high,
            location=orm.location,
            remote=orm.remote,
            seniority=cast(Seniority, orm.seniority),
            round_posted=orm.round_posted,
            round_expires=orm.round_expires,
            status=cast(PostingStatus, orm.status),
            is_ghost=orm.is_ghost,
            actual_budget=orm.actual_budget,
        )

    def _orm_application_to_pydantic(self, orm: ApplicationModel) -> ApplicationRecord:
        return ApplicationRecord(
            id=str(orm.id),
            job_seeker_id=str(orm.job_seeker_id),
            posting_id=str(orm.posting_id),
            recruiter_id=str(orm.recruiter_id) if orm.recruiter_id else None,
            resume_version_id=str(orm.resume_version_id),
            cover_letter_version_id=(
                str(orm.cover_letter_version_id) if orm.cover_letter_version_id else None
            ),
            round_submitted=orm.round_submitted,
            status=cast(ApplicationStatus, orm.status),
            status_updated_round=orm.status_updated_round,
        )

    def _orm_message_to_pydantic(self, orm: MessageModel) -> RecruiterHMMessage:
        return RecruiterHMMessage(
            id=str(orm.id),
            sender_id=str(orm.sender_id),
            receiver_id=str(orm.receiver_id),
            round_sent=orm.round_sent,
            content=orm.content,
            message_type=cast(MessageType, orm.message_type),
            posting_id=str(orm.posting_id),
            related_application_id=(
                str(orm.related_application_id) if orm.related_application_id else None
            ),
        )

    async def _load_open_postings(self) -> list[JobPosting]:
        stmt = select(JobPostingModel).where(
            JobPostingModel.run_id == self._run_id,
            JobPostingModel.status == "open",
        )
        result = await self._session.execute(stmt)
        orm_postings = result.scalars().all()
        return [await self._orm_posting_to_pydantic(p) for p in orm_postings]

    async def _load_applications_for_postings(
        self, posting_ids: list[uuid_mod.UUID]
    ) -> list[ApplicationRecord]:
        if not posting_ids:
            return []
        stmt = select(ApplicationModel).where(
            ApplicationModel.run_id == self._run_id,
            ApplicationModel.posting_id.in_(posting_ids),
        )
        result = await self._session.execute(stmt)
        return [self._orm_application_to_pydantic(a) for a in result.scalars().all()]

    async def _load_forwarded_applications(
        self, posting_ids: list[uuid_mod.UUID]
    ) -> list[ApplicationRecord]:
        if not posting_ids:
            return []
        stmt = select(ApplicationModel).where(
            ApplicationModel.run_id == self._run_id,
            ApplicationModel.posting_id.in_(posting_ids),
            ApplicationModel.status.in_(["reviewed", "advanced"]),
        )
        result = await self._session.execute(stmt)
        return [self._orm_application_to_pydantic(a) for a in result.scalars().all()]

    async def _load_messages_for_agent(self, agent_id: uuid_mod.UUID) -> list[RecruiterHMMessage]:
        stmt = (
            select(MessageModel)
            .where(
                MessageModel.run_id == self._run_id,
                (MessageModel.sender_id == agent_id) | (MessageModel.receiver_id == agent_id),
            )
            .order_by(MessageModel.round_sent)
        )
        result = await self._session.execute(stmt)
        return [self._orm_message_to_pydantic(m) for m in result.scalars().all()]

    async def _build_job_seeker_info(
        self, job_seeker_ids: set[str | uuid_mod.UUID]
    ) -> dict[str, dict[str, str]]:
        if not job_seeker_ids:
            return {}

        uuid_ids = [self._to_uuid(sid) for sid in job_seeker_ids]
        stmt = select(Agent).where(Agent.id.in_(uuid_ids))
        result = await self._session.execute(stmt)
        agents = result.scalars().all()

        info = {}
        for agent in agents:
            resume = ""
            if agent.state and isinstance(agent.state, dict):
                resume = agent.state.get("current_resume", "")
            info[str(agent.id)] = {
                "name": agent.name,
                "resume": resume or "",
            }
        return info

    async def _build_recruiter_info(self, messages: list[RecruiterHMMessage]) -> dict[str, str]:
        recruiter_ids = set()
        for msg in messages:
            recruiter_ids.add(msg.sender_id)
            recruiter_ids.add(msg.receiver_id)

        if not recruiter_ids:
            return {}

        uuid_ids = [self._to_uuid(rid) for rid in recruiter_ids]
        stmt = select(Agent.id, Agent.name).where(
            Agent.id.in_(uuid_ids),
            Agent.agent_type == "recruiter",
        )
        result = await self._session.execute(stmt)
        return {str(row.id): row.name for row in result.all()}

    async def _get_company_name(self, company_id: uuid_mod.UUID) -> str:
        stmt = select(Company.name).where(Company.id == company_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return row or "Unknown"

    async def _load_company(self, company_id: uuid_mod.UUID) -> Company | None:
        stmt = select(Company).where(Company.id == company_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_posting_company_id(self, posting_id: str) -> uuid_mod.UUID | None:
        stmt = select(JobPostingModel.company_id).where(
            JobPostingModel.id == self._to_uuid(posting_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_agent_company_ids(self) -> set[str]:
        if self._agent_company_ids is not None:
            return self._agent_company_ids

        stmt = select(Recruiter.company_id).where(Recruiter.run_id == self._run_id)
        result = await self._session.execute(stmt)
        self._agent_company_ids = {str(cid) for cid in result.scalars().all()}
        return self._agent_company_ids

    async def _build_posting_recruiter_map(
        self,
    ) -> dict[str, uuid_mod.UUID]:
        stmt = select(JobPostingModel.id, JobPostingModel.recruiter_id).where(
            JobPostingModel.run_id == self._run_id
        )
        result = await self._session.execute(stmt)
        return {str(row.id): row.recruiter_id for row in result.all()}

    async def _save_agent_state(self, agent_id: str, state: AgentState) -> None:
        stmt = (
            update(Agent)
            .where(Agent.id == self._to_uuid(agent_id))
            .values(state=state.model_dump())
        )
        await self._session.execute(stmt)

    async def persist_events(self, events: list[EventEntry]) -> None:
        for event in events:
            self._session.add(
                EventModel(
                    id=self._to_uuid(event.id),
                    run_id=self._run_id,
                    agent_id=(self._to_uuid(event.agent_id) if event.agent_id else None),
                    round_number=event.round_number,
                    event_type=event.event_type,
                    details=event.details,
                    created_at=event.created_at,
                )
            )

    async def _update_application_statuses(self, applications: list[ApplicationRecord]) -> None:
        for app in applications:
            if app.status_updated_round is not None:
                stmt = (
                    update(ApplicationModel)
                    .where(ApplicationModel.id == self._to_uuid(app.id))
                    .values(
                        status=app.status,
                        status_updated_round=app.status_updated_round,
                    )
                )
                await self._session.execute(stmt)

    async def find_pending_interviews(self, round_number):
        """Finds applications ready for interview that have no record yet.

        Queries for applications with status "advanced" in this run
        that do not have a corresponding Interview row. Joins to the
        job_postings table to identify the hiring manager who will
        conduct the interview.

        Args:
            round_number: The current simulation round, used as
                round_scheduled if the application doesn't have a
                status_updated_round.

        Returns:
            List of PendingInterview objects describing each interview
            to schedule.
        """
        from sqlalchemy import select

        from models.company import JobPosting as JobPostingModel
        from models.records import (
            Application as ApplicationModel,
        )
        from models.records import (
            Interview as InterviewModel,
        )

        interview_exists = (
            select(InterviewModel.id)
            .where(InterviewModel.application_id == ApplicationModel.id)
            .exists()
        )

        stmt = (
            select(
                ApplicationModel.id,
                ApplicationModel.job_seeker_id,
                ApplicationModel.posting_id,
                ApplicationModel.status_updated_round,
                JobPostingModel.hiring_manager_id,
            )
            .join(
                JobPostingModel,
                ApplicationModel.posting_id == JobPostingModel.id,
            )
            .where(
                ApplicationModel.run_id == self._run_id,
                ApplicationModel.status == "advanced",
                ~interview_exists,
            )
        )

        result = await self._session.execute(stmt)
        rows = result.all()

        pending = []
        for row in rows:
            pending.append(
                PendingInterview(
                    application_id=str(row.id),
                    job_seeker_id=str(row.job_seeker_id),
                    posting_id=str(row.posting_id),
                    interviewer_id=str(row.hiring_manager_id),
                    interviewer_type="hiring_manager",
                    round_scheduled=row.status_updated_round or round_number,
                )
            )

        return pending

    async def persist_interview(
        self,
        pending,
        round_conducted,
        transcript,
        interviewer_assessment,
        candidate_assessment,
        outcome,
    ):
        """Persists a completed interview to the database.

        Creates an Interview ORM record from the orchestrator's result
        and the scheduling metadata.

        Args:
            pending: The PendingInterview that triggered this interview.
            round_conducted: The round the interview took place.
            transcript: List of speaker/content dicts from the
                conversation.
            interviewer_assessment: The interviewer's written assessment.
            candidate_assessment: The candidate's written self-assessment.
            outcome: The parsed hiring decision string.
        """
        import uuid as uuid_mod

        from models.records import Interview as InterviewModel

        self._session.add(
            InterviewModel(
                id=uuid_mod.uuid4(),
                run_id=self._run_id,
                application_id=self._to_uuid(pending.application_id),
                interviewer_id=self._to_uuid(pending.interviewer_id),
                interviewer_type=pending.interviewer_type,
                round_scheduled=pending.round_scheduled,
                round_conducted=round_conducted,
                transcript=transcript,
                interviewer_evaluation=interviewer_assessment,
                candidate_evaluation=candidate_assessment,
                outcome=outcome,
            )
        )

    @staticmethod
    def _to_uuid(value: str | uuid_mod.UUID) -> uuid_mod.UUID:
        if isinstance(value, uuid_mod.UUID):
            return value
        return uuid_mod.UUID(value)
