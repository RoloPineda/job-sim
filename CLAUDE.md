# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

job-sim is an AI-agent simulation of the hiring market. AI agents (jobseekers, recruiters, hiring managers) interact autonomously through a round-based simulation, producing behavioral data about how hiring dynamics evolve over time.

## Build & Run Commands

- **Package manager:** uv (Python 3.11+)
- **Install deps:** `uv sync`
- **Run tests:** `uv run pytest`
- **Lint:** `uv run ruff check`
- **Format:** `uv run ruff format`


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
- You are forbidden from using separator comments
- 
## License

CC BY-NC-SA 4.0 — non-commercial with attribution, derivatives must use same license.