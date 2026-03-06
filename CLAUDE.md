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

### Key Design Patterns

- **Agent extensibility:** New agent types only need to implement the four abstract methods on BaseAgent. The interview engine and simulation engine work against the abstract interface.
- **State management:** Each agent has an AgentState (compressed_history + recent_events + metrics). History compression is periodic and configurable. Every round produces a StateSnapshot for the full observability timeline.
- **Hidden information:** PostingConfig has attributes (is_ghost, actual_budget) that are stripped before agents see them, enabling simulation of real-world information asymmetry.
- **Observability as data:** ResumeVersion, ReflectionEntry, and EventEntry tables capture behavioral evolution — resume rewrites, self-assessments, and all discrete events are append-only records.


### Style guides
- You must use the Google style guide for Python
- You must use Google Docstrings
- You must follow PEP conventions
- You must use typehints 
- You must ensure that docstrings are relevant and not regurgitate what's on the function definition
- Comments should be used carefully to explain things like magic numbers or why a decision was made to do it a certain way, or to explain things that are not easy to understand by reading the code


## License

CC BY-NC-SA 4.0 — non-commercial with attribution, derivatives must use same license.