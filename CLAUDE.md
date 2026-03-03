# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Candor** (job-sim) is an AI-agent simulation of the hiring market. AI agents (job seekers, recruiters, hiring managers) interact autonomously through a round-based simulation, producing behavioral data about how hiring dynamics evolve over time. The technical specification lives in `design-doc.md`.

## Build & Run Commands

- **Package manager:** uv (Python 3.14+)
- **Install deps:** `uv sync`
- **Run simulation:** `uv run python scripts/run_simulation.py`
- **Seed database:** `uv run python scripts/seed_database.py`
- **Export data:** `uv run python scripts/export_data.py`
- **Infrastructure:** `docker-compose up` (Postgres + simulation containers)

No test framework or linter is configured yet.

## Architecture

### Core Flow

`scripts/run_simulation.py` → `src/main.py` → `SimulationEngine.run()` → round loop → agent turns → API calls → tool execution → state persistence

### Key Layers

1. **Data Models** (`src/models/`) — Four Pydantic model files:
   - `market.py`: CompanyProfile, PostingConfig (includes hidden attributes like is_ghost, is_underpaid)
   - `agents.py`: AgentProfile, JobSeekerProfile, RecruiterProfile, HiringManagerProfile, AgentState
   - `interactions.py`: ApplicationRecord, InterviewRecord, OfferRecord, RecruiterHMMessage
   - `observability.py`: StateSnapshot, ResumeVersion, ReflectionEntry, EventEntry, RunConfig

2. **Agents** (`src/agents/`) — BaseAgent (abstract) with four abstract methods:
   - `get_tools()` — tool definitions for the Anthropic API
   - `build_context()` — agent-specific prompt context
   - `handle_tool_call()` — execute a tool call and return result
   - `evaluate()` — structured assessment after interactions

   Three implementations: JobSeekerAgent (12 tools), RecruiterAgent (7 tools), HiringManagerAgent (7 tools). All concrete infrastructure (API calls, state load/save, compression, reflection) lives in BaseAgent.

3. **Engine** (`src/engine/`) — Orchestration layer:
   - `simulation.py`: Round loop — board update → seekers act → recruiters act → HMs act → interviews → offers → state updates → reflections → snapshots
   - `job_board.py`: Posting lifecycle (publish, expire, ghost handling, visibility filtering)
   - `interview.py`: Multi-turn conversation engine between any two BaseAgent types, with turn floor/ceiling, wrap-up detection, and dual evaluations
   - `state_manager.py`: State updates, history compression, metrics computation
   - `prompt_builder.py`: Assembles system/user messages and tool definitions for the Anthropic API

4. **Seeding** (`src/seeding/`) — Data generation: Greenhouse API scraping, synthetic company/agent generation

### Key Design Patterns

- **Agent extensibility:** New agent types only need to implement the four abstract methods on BaseAgent. The interview engine and simulation engine work against the abstract interface.
- **State management:** Each agent has an AgentState (compressed_history + recent_events + metrics). History compression is periodic and configurable. Every round produces a StateSnapshot for the full observability timeline.
- **Hidden information:** PostingConfig has attributes (is_ghost, actual_budget) that are stripped before agents see them, enabling simulation of real-world information asymmetry.
- **Observability as data:** ResumeVersion, ReflectionEntry, and EventEntry tables capture behavioral evolution — resume rewrites, self-assessments, and all discrete events are append-only records.

### Dependencies

Core: anthropic, pydantic, psycopg/asyncpg, httpx, pyyaml

### Style guides
- You must use the Google style guide for Python
- You must use Google Docstrings
- You must follow PEP conventions
- You must use typehints 
- You must ensure that docstrings are relevant and not regurgitate what's on the function definition
- Comments should be used carefully to explain things like magic numbers or why a decision was made to do it a certain way, or to explain things that are not easy to understand by reading the code

### Branching rules
Always create a new branch from main before starting work. USe conventional commits. Naming convention feature/module-name. Commit frequently. Never work directly on main.

## License

CC BY-NC-SA 4.0 — non-commercial with attribution, derivatives must use same license.