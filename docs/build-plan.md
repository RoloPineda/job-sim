# Build Plan

Modules listed in implementation order. Each phase must be complete before the next begins. Modules within a phase can be built in parallel. Dependencies (pyproject.toml) are added incrementally as each phase introduces new packages.

## Phase 1: Project Setup

| Module | Dependencies | Status |
|---|---|---|
| `pyproject.toml` (add pydantic, pyyaml) | — | not started |
| `config/default_config.yaml` | — | not started |

## Phase 2: Data Models

No internal dependencies — pure Pydantic definitions. Build in any order.

| Module | Dependencies | Status |
|---|---|---|
| `src/models/market.py` | pydantic | not started |
| `src/models/agents.py` | pydantic | not started |
| `src/models/interactions.py` | pydantic | not started |
| `src/models/observability.py` | pydantic | not started |

## Phase 3: Config & Database

Add psycopg/asyncpg to pyproject.toml.

| Module | Dependencies | Status |
|---|---|---|
| `src/config.py` | `models/observability.py` (RunConfig) | not started |
| `src/db.py` | all models (schema creation + query helpers) | not started |

## Phase 4: Engine Utilities & Agent Base

Add anthropic to pyproject.toml.

| Module | Dependencies | Status |
|---|---|---|
| `src/engine/prompt_builder.py` | models, config | not started |
| `src/engine/state_manager.py` | models, db, config | not started |
| `src/engine/job_board.py` | models, db, config | not started |
| `src/agents/base.py` | models, db, config, prompt_builder | not started |

## Phase 5: Agent Implementations

All three depend on `agents/base.py`. Can be built in parallel.

| Module | Dependencies | Status |
|---|---|---|
| `src/agents/job_seeker.py` | agents/base, models, db | not started |
| `src/agents/recruiter.py` | agents/base, models, db | not started |
| `src/agents/hiring_manager.py` | agents/base, models, db | not started |

## Phase 6: Orchestration Engines

| Module | Dependencies | Status |
|---|---|---|
| `src/engine/interview.py` | agents/base, models, config | not started |
| `src/engine/simulation.py` | all engine modules, all agents | not started |

## Phase 7: Seeding

Add httpx to pyproject.toml.

| Module | Dependencies | Status |
|---|---|---|
| `src/seeding/greenhouse.py` | models, httpx | not started |
| `src/seeding/company_generator.py` | models, db | not started |
| `src/seeding/agent_generator.py` | models, db | not started |

## Phase 8: Entry Points & Scripts

| Module | Dependencies | Status |
|---|---|---|
| `src/main.py` | config, db, agents, engine | not started |
| `scripts/seed_database.py` | config, db, seeding | not started |
| `scripts/run_simulation.py` | main | not started |
| `scripts/export_data.py` | config, db, models | not started |

## Phase 9: Infrastructure

| Module | Dependencies | Status |
|---|---|---|
| `Dockerfile` | working application | not started |
| `docker-compose.yml` | Dockerfile | not started |