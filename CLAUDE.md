# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Candor** (job-sim) is an AI-agent simulation of the hiring market. AI agents (job seekers, recruiters, hiring managers) interact autonomously through a round-based simulation, producing behavioral data about how hiring dynamics evolve over time. The technical specification lives in `design-doc.md`.

## Build & Run Commands

- **Package manager:** uv (Python 3.14+)
- **Install deps:** `uv sync`
- **Run tests:** `uv run pytest`
- **Lint:** `uv run ruff check`
- **Format:** `uv run ruff format`
- **Run simulation:** `uv run python scripts/run_simulation.py`
- **Seed database:** `uv run python scripts/seed_database.py`
- **Export data:** `uv run python scripts/export_data.py`
- **Run migrations:** `uv run alembic upgrade head`
- **Infrastructure:** `docker-compose up` (Postgres + simulation containers)

## Architecture

### Core Flow

`scripts/run_simulation.py` → `src/main.py` → `SimulationEngine.run()` → round loop → agent turns → API calls → tool execution → state persistence

### Key Layers

1. **Pydantic Schemas** (`src/schemas/`) — Validation and serialization models:
   - `types.py`: Shared `AgentType` literal
   - `agents.py`: AgentProfile, JobSeekerProfile, RecruiterProfile, HiringManagerProfile, AgentState
   - `company.py`: CompanyProfile, JobPosting (includes hidden attributes like is_ghost, actual_budget)
   - `config.py`: RunConfig (frozen simulation parameters)
   - `records.py`: ApplicationRecord, InterviewRecord, OfferRecord, RecruiterHMMessage, ResumeVersion, CoverLetterVersion, StateSnapshot, ReflectionEntry, EventEntry

2. **Database** (`src/models/`, `alembic/`) — SQLAlchemy ORM models and Alembic migrations (in progress)

3. **Agents** (`src/agents/`) — BaseAgent (abstract) with four abstract methods:
   - `get_tools()` — tool definitions for the Anthropic API
   - `build_context()` — agent-specific prompt context
   - `handle_tool_call()` — execute a tool call and return result
   - `evaluate()` — structured assessment after interactions

   Three implementations: JobSeekerAgent (12 tools), RecruiterAgent (7 tools), HiringManagerAgent (7 tools). All concrete infrastructure (API calls, state load/save, compression, reflection) lives in BaseAgent.

4. **Engine** (`src/engine/`) — Orchestration layer:
   - `simulation.py`: Round loop — board update → seekers act → recruiters act → HMs act → interviews → offers → state updates → reflections → snapshots
   - `job_board.py`: Posting lifecycle (publish, expire, ghost handling, visibility filtering)
   - `interview.py`: Multi-turn conversation engine between any two BaseAgent types
   - `state_manager.py`: State updates, history compression, metrics computation
   - `prompt_builder.py`: Assembles system/user messages and tool definitions for the Anthropic API

5. **Seeding** (`src/seeding/`) — Data generation: Greenhouse API scraping, synthetic company/agent generation

### Key Design Patterns

- **Agent extensibility:** New agent types only need to implement the four abstract methods on BaseAgent. The interview engine and simulation engine work against the abstract interface.
- **State management:** Each agent has an AgentState (compressed_history + recent_events + metrics). History compression is periodic and configurable. Every round produces a StateSnapshot for the full observability timeline.
- **Hidden information:** JobPosting has attributes (is_ghost, actual_budget) that are stripped before agents see them, enabling simulation of real-world information asymmetry.
- **Observability as data:** ResumeVersion, ReflectionEntry, and EventEntry capture behavioral evolution — resume rewrites, self-assessments, and all discrete events are append-only records.

### Dependencies

Core: pydantic, alembic, pyyaml
Planned: anthropic, psycopg/asyncpg, httpx
Dev: pytest, ruff

### Style guides
- You must use the Google style guide for Python
- You must use Google Docstrings
- You must follow PEP conventions
- You must use typehints 
- You must ensure that docstrings are relevant and not regurgitate what's on the function definition
- Comments should be used carefully to explain things like magic numbers or why a decision was made to do it a certain way, or to explain things that are not easy to understand by reading the code


### Branching rules
Always create a new branch from main before starting work. Use conventional commits. Naming convention `feature/module-name`. Commit frequently. Never work directly on main. Do not add yourself as contributor/author.

## License

CC BY-NC-SA 4.0 — non-commercial with attribution, derivatives must use same license.