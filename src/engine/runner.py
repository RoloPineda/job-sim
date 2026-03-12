"""Simulation runner that orchestrates the round loop.

Constructs agents from database state, runs turns concurrently by
agent type, collects side effects, handles background company
responses, triggers compression and reflections, and persists
everything through the state manager.
"""

import asyncio
import logging
import random
import uuid as uuid_mod
from datetime import datetime, timezone

from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.hiring_manager import HiringManagerAgent
from agents.job_seeker import JobSeekerAgent
from agents.recruiter import RecruiterAgent
from engine.compression import compress_history, should_compress
from engine.prompt_builder import PromptBuilder
from engine.state_manager import (
    BackgroundOutcome,
    HiringManagerBundle,
    JobSeekerBundle,
    RecruiterBundle,
    StateManager,
)
from models.agents import Agent
from schemas.config import RunConfig
from schemas.company import JobPosting
from schemas.profiles import AgentProfile
from schemas.records import ApplicationRecord, EventEntry

logger = logging.getLogger(__name__)


class SimulationRunner:
    """Runs a complete simulation from round 1 through total_rounds.

    Manages the per-round lifecycle: hydrate agents, compress history,
    run turns by agent type with concurrency, persist side effects,
    process background company outcomes, run reflections, and write
    snapshots.

    Args:
        session: SQLAlchemy async session for the run. The runner
            commits after each round.
        run_id: The simulation run to execute.
        config: Simulation-wide parameters.
        client: Anthropic async client shared across all agents.
    """

    def __init__(
        self,
        session: AsyncSession,
        run_id: uuid_mod.UUID,
        config: RunConfig,
        client: AsyncAnthropic,
    ) -> None:
        self._session = session
        self._run_id = run_id
        self._config = config
        self._client = client
        self._state_manager = StateManager(session, run_id, config)
        self._pending_background: dict[str, BackgroundOutcome] = {}

    async def run(self) -> None:
        """Executes the simulation from round 1 through total_rounds."""
        logger.info(
            "Starting simulation %s for %d rounds",
            self._run_id,
            self._config.total_rounds,
        )

        for round_number in range(1, self._config.total_rounds + 1):
            logger.info("Round %d starting", round_number)
            await self._run_round(round_number)
            await self._session.commit()
            logger.info("Round %d complete", round_number)

        logger.info("Simulation %s finished", self._run_id)

    async def _run_round(self, round_number: int) -> None:
        """Executes a single simulation round.

        Args:
            round_number: The current round to execute.
        """
        await self._process_background_outcomes(round_number)

        job_seeker_bundles = await self._state_manager.load_job_seeker_bundles(
            round_number
        )
        open_postings = await self._state_manager.load_open_postings()
        recruiter_bundles = await self._state_manager.load_recruiter_bundles(
            round_number
        )
        hm_bundles = await self._state_manager.load_hm_bundles(round_number)

        if (
            round_number > 1
            and round_number % self._config.compression_frequency == 0
        ):
            await self._compress_all(
                job_seeker_bundles, recruiter_bundles, hm_bundles
            )

        await self._run_job_seeker_turns(
            job_seeker_bundles, open_postings, round_number
        )
        await self._run_recruiter_turns(recruiter_bundles, round_number)
        await self._run_hm_turns(hm_bundles, round_number)

        if round_number % self._config.reflection_frequency == 0:
            await self._run_reflections(
                job_seeker_bundles, recruiter_bundles, hm_bundles, round_number
            )

        await self._state_manager.write_snapshots(round_number)

    async def _run_job_seeker_turns(
        self,
        bundles: list[JobSeekerBundle],
        postings: list[JobPosting],
        round_number: int,
    ) -> None:
        """Runs all job seeker turns concurrently and persists results.

        Args:
            bundles: Job seeker data bundles for the round.
            postings: Open postings shared across all job seekers.
            round_number: Current round.
        """
        agents = [
            JobSeekerAgent(
                profile=b.profile,
                config=self._config,
                state=b.state,
                postings=postings,
                client=self._client,
            )
            for b in bundles
        ]

        await asyncio.gather(
            *[a.run_turn(round_number) for a in agents]
        )

        all_resumes = []
        all_applications = []
        for agent in agents:
            all_resumes.extend(agent.resume_versions)
            all_applications.extend(agent.applications)

        applications = await self._state_manager.persist_job_seeker_results(
            bundles, all_resumes, all_applications, round_number
        )

        await self._schedule_background_outcomes(
            applications, round_number
        )

    async def _run_recruiter_turns(
        self, bundles: list[RecruiterBundle], round_number: int
    ) -> None:
        """Runs all recruiter turns concurrently and persists results.

        Args:
            bundles: Recruiter data bundles for the round.
            round_number: Current round.
        """
        agents = [
            RecruiterAgent(
                profile=b.profile,
                config=self._config,
                state=b.state,
                postings=b.postings,
                applications=b.applications,
                hm_messages=b.hm_messages,
                job_seeker_info=b.job_seeker_info,
                client=self._client,
            )
            for b in bundles
        ]

        await asyncio.gather(
            *[a.run_turn(round_number) for a in agents]
        )

        all_messages = []
        all_events = []
        modified_apps = []
        for agent, bundle in zip(agents, bundles):
            all_messages.extend(agent.hm_messages_sent)
            all_events.extend(agent.events_created)
            modified_apps.extend(self._find_modified_apps(bundle.applications))

        await self._state_manager.persist_recruiter_results(
            bundles, all_messages, all_events, modified_apps
        )

    async def _run_hm_turns(
        self, bundles: list[HiringManagerBundle], round_number: int
    ) -> None:
        """Runs all hiring manager turns concurrently and persists results.

        Args:
            bundles: HM data bundles for the round.
            round_number: Current round.
        """
        agents = [
            HiringManagerAgent(
                profile=b.profile,
                config=self._config,
                state=b.state,
                postings=b.postings,
                applications=b.applications,
                recruiter_messages=b.recruiter_messages,
                seeker_info=b.job_seeker_info,
                recruiter_info=b.recruiter_info,
                client=self._client,
            )
            for b in bundles
        ]

        await asyncio.gather(
            *[a.run_turn(round_number) for a in agents]
        )

        all_messages = []
        all_events = []
        modified_apps = []
        for agent, bundle in zip(agents, bundles):
            all_messages.extend(agent.hm_messages_sent)
            all_events.extend(agent.events_created)
            modified_apps.extend(self._find_modified_apps(bundle.applications))

        await self._state_manager.persist_hm_results(
            bundles, all_messages, all_events, modified_apps
        )

    async def _schedule_background_outcomes(
        self,
        applications: list[ApplicationRecord],
        round_number: int,
    ) -> None:
        """Schedules delayed responses for background company applications.

        Ghost companies never respond. Other background companies
        reject after a delay computed from their response parameters.

        Args:
            applications: All applications submitted this round.
            round_number: Current round.
        """
        background_apps = (
            await self._state_manager.detect_background_applications(
                applications
            )
        )

        for app, responsiveness, company_id in background_apps:
            if responsiveness == "ghosts":
                self._pending_background[app.id] = BackgroundOutcome(
                    application_id=app.id,
                    job_seeker_id=app.job_seeker_id,
                    posting_id=app.posting_id,
                    posting_title=app.posting_id,
                    round_due=-1,
                    outcome="ghosted",
                )
                continue

            base_delay, variance = (
                await self._state_manager.load_company_response_params(
                    company_id
                )
            )
            jitter = random.randint(-variance, variance)
            delay = max(1, base_delay + jitter)

            self._pending_background[app.id] = BackgroundOutcome(
                application_id=app.id,
                job_seeker_id=app.job_seeker_id,
                posting_id=app.posting_id,
                posting_title=app.posting_id,
                round_due=round_number + delay,
                outcome="rejected",
            )

    async def _process_background_outcomes(
        self, round_number: int
    ) -> None:
        """Fires background outcomes that are due this round.

        Creates rejection events for seekers. Ghosted applications
        are left in limbo indefinitely.

        Args:
            round_number: Current round.
        """
        due = [
            outcome
            for outcome in self._pending_background.values()
            if outcome.round_due == round_number
        ]

        for outcome in due:
            event = EventEntry(
                id=str(uuid_mod.uuid4()),
                agent_id=outcome.job_seeker_id,
                round_number=round_number,
                event_type=f"application_{outcome.outcome}",
                details={
                    "application_id": outcome.application_id,
                    "posting_id": outcome.posting_id,
                    "posting_title": outcome.posting_title,
                    "message": (
                        "Thank you for your interest. After careful "
                        "consideration, we've decided to move forward "
                        "with other candidates."
                    ),
                    "from_background_company": True,
                },
                created_at=datetime.now(timezone.utc),
            )
            await self._state_manager.persist_events([event])
            del self._pending_background[outcome.application_id]

            logger.info(
                "Background %s for application %s (seeker %s)",
                outcome.outcome,
                outcome.application_id,
                outcome.job_seeker_id,
            )

    async def _compress_all(
        self,
        job_seeker_bundles: list[JobSeekerBundle],
        recruiter_bundles: list[RecruiterBundle],
        hm_bundles: list[HiringManagerBundle],
    ) -> None:
        """Compresses history for all agents.

        Args:
            job_seeker_bundles: Job seeker data for the round.
            recruiter_bundles: Recruiter data for the round.
            hm_bundles: HM data for the round.
        """
        tasks = []
        for b in job_seeker_bundles:
            if should_compress(b.state, self._config):
                tasks.append(compress_history(
                    b.state, self._config, self._client, b.profile.id
                ))
        for b in recruiter_bundles:
            if should_compress(b.state, self._config):
                tasks.append(compress_history(
                    b.state, self._config, self._client, b.profile.id
                ))
        for b in hm_bundles:
            if should_compress(b.state, self._config):
                tasks.append(compress_history(
                    b.state, self._config, self._client, b.profile.id
                ))

        if tasks:
            await asyncio.gather(*tasks)
            logger.info("Compressed history for %d agents", len(tasks))

    async def _run_reflections(
        self,
        job_seeker_bundles: list[JobSeekerBundle],
        recruiter_bundles: list[RecruiterBundle],
        hm_bundles: list[HiringManagerBundle],
        round_number: int,
    ) -> None:
        """Runs reflection prompts for all agents and persists results.

        Args:
            job_seeker_bundles: Job seeker data for the round.
            recruiter_bundles: Recruiter data for the round.
            hm_bundles: HM data for the round.
            round_number: Current round.
        """
        all_agents: list[tuple[str, str, str, str]] = []
        for b in job_seeker_bundles:
            all_agents.append((
                b.profile.id,
                b.profile.agent_type,
                b.state.compressed_history,
                b.profile.name,
            ))
        for b in recruiter_bundles:
            all_agents.append((
                b.profile.id,
                b.profile.agent_type,
                b.state.compressed_history,
                b.profile.name,
            ))
        for b in hm_bundles:
            all_agents.append((
                b.profile.id,
                b.profile.agent_type,
                b.state.compressed_history,
                b.profile.name,
            ))

        builder = PromptBuilder(self._config)

        for agent_id, agent_type, context_summary, name in all_agents:
            stmt = select(Agent).where(
                Agent.id == StateManager._to_uuid(agent_id)
            )
            result = await self._session.execute(stmt)
            agent_orm = result.scalar_one_or_none()
            if not agent_orm:
                continue

            profile = AgentProfile(
                id=str(agent_orm.id),
                agent_type=agent_orm.agent_type,
                name=agent_orm.name,
                disposition=agent_orm.disposition,
                backstory=agent_orm.backstory,
                location=agent_orm.location,
            )

            payload = builder.build_reflection_prompt(
                profile, context_summary or "No prior context."
            )

            response = await self._client.messages.create(
                model=self._config.sonnet_model_version,
                system=payload["system"],
                messages=payload["messages"],
                max_tokens=1024,
            )

            reflection_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    reflection_text += block.text

            await self._state_manager.save_reflection(
                agent_id=agent_id,
                agent_type=agent_type,
                round_number=round_number,
                prompt_used=payload["messages"][0]["content"],
                response=reflection_text.strip(),
                context_summary=context_summary or "",
            )

            logger.info(
                "[%s] reflection generated (%d chars)",
                agent_id,
                len(reflection_text),
            )

    @staticmethod
    def _find_modified_apps(
        applications: list[ApplicationRecord],
    ) -> list[ApplicationRecord]:
        """Finds applications whose status was changed during the turn.

        Args:
            applications: The application list passed to the agent.

        Returns:
            Applications with a non-None status_updated_round.
        """
        return [
            app for app in applications
            if app.status_updated_round is not None
        ]