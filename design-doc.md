# Candor: Technical Architecture

This document covers the class design, data models, and code structure for the simulation. It's the technical companion to the main design document. It is intended to be used as a specification for implementation -- feed it to Claude Code alongside the main design document.

## License

CC BY-NC-SA 4.0. Free to use for non-commercial purposes with attribution. Derivatives must use the same license.

## Project Structure

The project uses uv for dependency management. The top-level layout:

- `docker-compose.yml` -- Postgres container with mounted volume, plus the simulation container
- `Dockerfile` -- Python environment for the simulation
- `pyproject.toml` -- uv-managed dependencies: anthropic, pydantic, psycopg (or asyncpg), httpx (for Greenhouse API calls)
- `config/default_config.yaml` -- default simulation parameters
- `src/` -- all source code
- `scripts/` -- entry points for seeding, running, and exporting
- `analysis/notebooks/` -- Jupyter notebooks for post-run exploration

Inside `src/`:

- `main.py` -- entry point
- `config.py` -- loads and validates RunConfig from YAML
- `db.py` -- database connection, schema creation, query helpers
- `models/` -- Pydantic data models split across four files: `agents.py`, `interactions.py`, `market.py`, `observability.py`
- `agents/` -- agent classes: `base.py` (abstract base), `job_seeker.py`, `recruiter.py`, `hiring_manager.py`
- `engine/` -- orchestration: `simulation.py`, `job_board.py`, `interview.py`, `prompt_builder.py`, `state_manager.py`
- `seeding/` -- data generation: `greenhouse.py` (API scraper), `company_generator.py`, `agent_generator.py`

Scripts directory has three entry points: `seed_database.py` (populates the database with companies, postings, and agents), `run_simulation.py` (executes a simulation run), and `export_data.py` (dumps run data for external analysis).

## Data Models (Pydantic)

These are the structured representations of everything in the simulation. They serve double duty: validation when creating/updating records, and serialization when reading from or writing to Postgres. All models use Google-style docstrings.

### Market Models (`models/market.py`)

**CompanyProfile** -- represents a company's identity and behavioral tendencies. Fields: id, name, industry, size (startup/mid/enterprise), growth_stage (early/scaling/mature), culture_description, budget_flexibility (rigid/moderate/flexible), responsiveness_pattern (fast/slow/unpredictable/ghosts), base_response_delay (rounds before typical response), response_delay_variance (randomness added to delay). This is the stable foundation that doesn't change during a simulation run. It influences how the company's recruiter and hiring manager agents behave, but is not modified by them.

**PostingConfig** -- represents a single job posting on the board. Fields: id, company_id, title, department, description, requirements (list of strings), salary_range_low (optional), salary_range_high (optional), location, remote (bool), seniority (junior/mid/senior/lead/staff), posted_round, expiry_round (optional), status (open/closed/filled/expired). Also includes hidden attributes that agents cannot see directly but that affect simulation behavior: is_ghost (bool, default false), is_underpaid (bool, default false), is_realistic (bool, default true), actual_budget (optional int). Ghost jobs accept applications but never advance candidates.

### Agent Models (`models/agents.py`)

**AgentProfile** -- base profile shared by all agent types. Fields: id, agent_type (job_seeker/recruiter/hiring_manager), name, disposition, backstory. Contains the stable identity and disposition that persist throughout the simulation. Accumulated experience is stored separately in AgentState.

**JobSeekerProfile** -- extends AgentProfile. Additional fields: actual_skills (list, ground truth used by the simulation for evaluating fit), perceived_skills (list, what the agent believes about itself, used in prompt context), experience_years, target_role, target_seniority, target_comp_low, target_comp_high, location_flexibility (rigid/moderate/flexible), financial_runway (rounds before desperation), communication_ability (strong/average/weak), self_awareness (accurate/overconfident/underconfident).

**RecruiterProfile** -- extends AgentProfile. Additional fields: company_id, hiring_manager_ids (list), assigned_posting_ids (list), experience_level (junior/mid/senior), current_workload (number of open roles managed).

**HiringManagerProfile** -- extends AgentProfile. Additional fields: company_id, team_size, team_situation (understaffed/stable/growing/rebuilding), management_style (detailed_feedback/vague/responsive/slow/micromanager), technical_bar (description of what they value), interview_capacity_per_round, past_hiring_description.

**AgentState** -- mutable state that evolves each round. Fields: round_number, compressed_history (summarized older events), recent_events (list of dicts, raw events from last N rounds), current_pipeline (list of dicts, active applications/interviews), current_resume (optional string, seekers only), metrics (dict, computed stats like application count and rejection rate), last_reflection (optional string). This is serialized to JSON and stored in both the agents table (current state) and state_snapshots table (historical record).

### Interaction Models (`models/interactions.py`)

**ApplicationRecord** -- links a job seeker to a posting through an application. Fields: id, seeker_id, posting_id, resume_version_id, cover_letter (optional), round_submitted, status (pending/reviewed/rejected/advanced/ghosted), status_updated_round (optional). Tracks the full lifecycle from submission through outcome.

**InterviewRecord** -- captures a complete interview interaction. Fields: id, application_id, interviewer_id, interviewer_type (recruiter/hiring_manager), round, transcript (list of speaker/content dicts), interviewer_evaluation (optional), candidate_evaluation (optional), outcome (advanced/rejected/undecided), turn_count. Stores the full transcript plus both agents' independent evaluations and reasoning.

**OfferRecord** -- tracks an offer and any negotiation that follows. Fields: id, application_id, round_extended, base_salary, total_comp (optional), role_title, negotiation_history (list of counter-offer dicts), final_outcome (accepted/declined/negotiating), round_resolved (optional).

**RecruiterHMMessage** -- communication between recruiter and hiring manager. Fields: id, sender_id, receiver_id, round, content, message_type (candidate_forward/feedback/nudge/role_change_request), related_application_id (optional). How a recruiter frames a candidate to the HM is itself behavioral data.

### Observability Models (`models/observability.py`)

**StateSnapshot** -- point-in-time capture of an agent's full state. Fields: agent_id, agent_type, round_number, state_json (dict, serialized AgentState), created_at (datetime). Written at the end of every round for every agent. Primary data source for tracking behavioral progression over time.

**ResumeVersion** -- a single version of a job seeker's resume. Fields: id, seeker_id, round_created, full_text, trigger (initial/general_rewrite/tailored/desperate_overhaul), target_posting_id (optional), state_summary_at_creation. Append-only table. Every call to write_resume creates a new row. The trigger field records why the rewrite happened, which is itself behavioral data.

**ReflectionEntry** -- an agent's periodic self-assessment. Fields: id, agent_id, agent_type, round_number, prompt_used, response, context_summary. Captures both the prompt used and the response, plus the context that was active when the reflection was generated. Primary source of quotable blog content.

**EventEntry** -- generic event log for any discrete occurrence. Fields: id, agent_id (optional), round_number, event_type, details (dict), created_at (datetime). Catch-all for everything that happens: application_submitted, rejection_sent, interview_scheduled, offer_extended, posting_closed, resume_updated, tool_called, etc.

**RunConfig** -- complete parameter set for a simulation run. Stored once at the start of each run. Makes runs reproducible and comparable. Contains model parameters (temperature, top_p, sonnet_model_version, haiku_model_version), context parameters (compression_frequency, recent_history_window, max_context_tokens), simulation structure parameters (turn_structure, agent_action_order, board_visibility, reflection_frequency, interview_turn_floor, interview_turn_ceiling), market parameters (seeker_to_opening_ratio, ghost_job_percentage, rejection_specificity, new_postings_per_round, posting_expiry_rounds), and scale parameters (num_seekers, num_companies, num_postings, total_rounds).

## Agent Classes

### Abstract Base (`agents/base.py`)

BaseAgent is an abstract class that provides shared infrastructure for API calls, state management, and logging. Subclasses implement the abstract methods to define agent-type-specific behavior. The abstract surface is intentionally small: four methods that genuinely differ between agent types. Everything else is concrete and shared.

**Constructor** takes an AgentProfile, a Database connection, and a RunConfig.

**Abstract methods (subclasses must implement):**

`get_tools` -- returns tool definitions formatted for the Anthropic API. Each agent type exposes different tools. A job seeker gets browse_job_board, write_resume, etc. A hiring manager gets review_forwarded_candidates, conduct_interview, etc.

`build_context` -- assembles the agent-specific portion of the prompt. Pulls from the agent's current state and formats it into context that gets injected into the user message. This is where seeker context (application history, resume, financial runway) differs from HM context (pipeline state, team pressure, candidate evaluations).

`handle_tool_call` -- executes a tool call and returns the result. When the API response includes a tool use block, this method performs the actual action (writing to the database, updating state, etc.) and returns a result that gets fed back to the model if needed.

`evaluate` -- produces a structured assessment after an interaction. Called after interviews, application reviews, or other evaluative moments. The agent receives the interaction transcript and generates its assessment, which gets logged as a decision trace.

**Concrete methods (shared across all agent types):**

`load_state` -- pulls current state from the database.

`save_state` -- writes current state back to the database.

`save_snapshot` -- writes a state snapshot for the observability timeline.

`build_system_prompt` -- assembles the system prompt from profile and disposition. Shared because the structure is the same for all agent types: identity, disposition, backstory, and general instructions.

`build_full_prompt` -- combines system prompt, context, and tools into an API-ready payload. Calls build_system_prompt for the system message, build_context for the user message content, and get_tools for the tool definitions.

`call_api` -- async method that calls the Anthropic API with retry logic, exponential backoff, and rate limit handling. Logs the raw request and response for debugging.

`compress_history` -- compresses older events in state into a summary. Called based on compression_frequency in config. Moves events outside the recent_history_window into compressed_history.

`reflect` -- runs a self-reflection prompt and logs the result. Called based on reflection_frequency in config. Builds a reflection prompt, sends it to the API, stores the response as a ReflectionEntry, and appends it to the agent's state for future context.

### Job Seeker (`agents/job_seeker.py`)

JobSeekerAgent extends BaseAgent. Represents a person searching for a job. Carries a resume that evolves over time, tracks application history and outcomes, and makes autonomous decisions about where to apply, how much effort to invest, and when to settle for less.

`get_tools` returns definitions for: browse_job_board, research_company, write_resume, write_cover_letter, submit_application, check_application_status, respond_to_recruiter, do_interview, evaluate_offer, negotiate_offer, accept_offer, decline_offer, reflect.

`build_context` includes: current resume, application history with outcomes, pending pipeline, financial runway remaining, compressed history, recent events, last reflection, and computed metrics (rejection rate, ghost rate, average response time experienced).

`handle_tool_call` key behaviors: write_resume saves a new ResumeVersion and updates state. submit_application creates an ApplicationRecord and links the current resume version. write_cover_letter saves the letter and attaches it to the pending application. accept_offer marks the search as complete and ends the agent's participation in future rounds.

`evaluate` produces a post-interview self-assessment: how it went, impressions of the company and interviewer, and whether the agent is still interested.

### Recruiter (`agents/recruiter.py`)

RecruiterAgent extends BaseAgent. Represents a recruiter managing open requisitions. Bridges job seekers and hiring managers. Develops its own mental model of what each hiring manager wants, which may drift from reality over time.

`get_tools` returns definitions for: screen_applications, forward_to_hiring_manager, post_or_adjust_listing, schedule_interview, manage_candidate_communication, nudge_hiring_manager, reflect.

`build_context` includes: assigned roles and their pipeline state, applications received per role, forwarding history and outcomes (what HM did with forwarded candidates), HM feedback history, current workload, compressed history, recent events.

`handle_tool_call` key behaviors: screen_applications reads pending applications and produces screening decisions. forward_to_hiring_manager creates a RecruiterHMMessage with candidate summary and framing. manage_candidate_communication sends updates or rejections to seekers with configurable delay. nudge_hiring_manager sends a follow-up message to the HM.

`evaluate` produces a post-interaction assessment: evaluates candidate fit based on the recruiter's understanding of HM preferences.

### Hiring Manager (`agents/hiring_manager.py`)

HiringManagerAgent extends BaseAgent. Represents a hiring manager making final decisions. Develops evaluation criteria organically based on accumulated experience. May become pickier, more lenient, or develop biases based on candidate exposure patterns.

`get_tools` returns definitions for: review_forwarded_candidates, conduct_interview, give_feedback_to_recruiter, approve_offer, reject_candidate, request_role_change, reflect.

`build_context` includes: team situation and pressure, candidates reviewed and their outcomes, interview history, feedback given to recruiter, time role has been open, compressed history, recent events.

`handle_tool_call` key behaviors: review_forwarded_candidates evaluates the recruiter's forwarded candidates and decides who to interview. give_feedback_to_recruiter produces feedback that shapes future screening (may be vague or specific based on management style). approve_offer sets comp within budget or argues for an exception. request_role_change adjusts requirements, level, or posting language.

`evaluate` produces a post-interview candidate assessment. Given the interview transcript, team needs, and accumulated evaluation experience, generates a structured assessment with reasoning. This is the primary data source for detecting emerging biases and shifting standards.

## Engine Classes

### Job Board (`engine/job_board.py`)

JobBoard manages the lifecycle of job postings. Not an agent. A data manager that the simulation engine calls at the start of each round to update what's visible on the board.

Constructor takes a Database connection and RunConfig.

`update` runs all board updates for a round: publishes new postings from the schedule, expires old ones, marks ghost jobs as silently dead after their configured lifespan, and updates status of filled roles.

`get_visible_postings` returns postings visible to job seekers. Filters by status (open only), respects board visibility settings from config (full vs. paginated), and applies any agent-requested filters (role type, seniority, etc.). Hidden attributes are stripped before returning.

`close_posting` marks a posting as closed with a reason (filled, abandoned, or paused).

`repost` creates a new posting from an existing one with modifications. The old posting is closed. Returns the new posting ID.

### Interview Engine (`engine/interview.py`)

InterviewEngine manages multi-turn conversations between agents. Handles the back-and-forth loop, turn limits, wrap-up detection, transcript capture, and post-interview evaluations from both sides.

Designed against the abstract BaseAgent interface so it works with any agent type combination: HM interviewing a candidate, recruiter doing a phone screen, or future agent types like panel interviews or technical screens.

Constructor takes a RunConfig and reads interview_turn_floor and interview_turn_ceiling from it.

`run_interview` is the main async method. Takes an interviewer (BaseAgent), a candidate (BaseAgent), and an interview_context dict. Returns an InterviewRecord. The flow is:

1. Build interviewer's opening prompt with candidate resume and role context.
2. Interviewer generates opening (question or intro).
3. Loop: append interviewer message to candidate context, candidate generates response, append candidate message to interviewer context, check if interviewer signals wrap-up. If wrap-up and above the floor, move to closing. If at the ceiling, inject a time cue and force wrap-up. Otherwise, interviewer generates next turn.
4. Candidate gets one final turn for closing questions.
5. Both agents evaluate independently via their evaluate method.
6. Return complete InterviewRecord with transcript, evaluations, and metadata.

`_detect_wrap_up` checks if a message signals the interview is ending. Looks for patterns like handing off to the candidate for questions, thanking for their time, or summarizing next steps.

`_build_time_cue` returns a message indicating time is running out. Injected when the turn ceiling is reached to prompt a natural conclusion.

### Simulation Engine (`engine/simulation.py`)

SimulationEngine is the main orchestration loop. Manages round progression, agent execution order, interview scheduling, state updates, and logging. This is procedural logic wrapped in a class for organizational purposes.

Constructor takes a RunConfig, Database, list of BaseAgent instances, a JobBoard, and an InterviewEngine.

`run` executes the full simulation for the configured number of rounds by calling run_round in sequence.

`run_round` executes a single round. The sequence is:

1. job_board.update -- new postings, expirations
2. Run each job seeker agent -- browse, apply, respond
3. Run each recruiter agent -- screen, forward, communicate
4. Run each hiring manager agent -- review, decide, feedback
5. Run scheduled interviews via interview_engine
6. Process offer/negotiation interactions
7. Update all agent states via state_manager
8. Run reflections for agents on the reflection schedule
9. Save state snapshots for all agents
10. Compress history for agents on the compression schedule
11. Log round summary

`_run_agent_turn` executes a single agent's turn within a round. Builds the full prompt, calls the API, parses tool calls from the response, executes each tool call via agent.handle_tool_call, and collects results. If the model makes multiple tool calls, they're executed in sequence.

`_get_pending_interviews` returns interviews scheduled for the current round.

`_schedule_interview` adds an interview to the schedule for a future round.

### State Manager (`engine/state_manager.py`)

StateManager handles state updates, compression, and snapshots. Separated from the simulation engine because the logic is complex enough to warrant its own home.

Constructor takes a Database connection and RunConfig.

`update_agent_state` applies round events to an agent's state. Appends new events to recent_events, updates metrics, and refreshes current_pipeline with any status changes.

`compress_if_needed` checks the compression schedule and compresses if due. Moves events outside the recent_history_window into compressed_history by summarizing them. The compression strategy is configurable and directly affects behavioral outcomes.

`compute_metrics` computes derived metrics from agent history. For seekers: total applications, rejection rate, ghost rate, average response time, rounds since last positive signal, current comp target vs. original. For recruiters: candidates screened, forward rate, HM rejection rate of forwarded candidates, average time to fill. For HMs: candidates reviewed, interview rate, offer rate, average rounds to decision, feedback specificity trend.

`save_snapshot` serializes and stores the current state snapshot.

### Prompt Builder (`engine/prompt_builder.py`)

PromptBuilder is a utility class for assembling API-ready prompts. Handles the mechanics of combining system messages, context, tool definitions, and conversation history into the format the Anthropic API expects.

Constructor takes a RunConfig.

`build_system_message` creates the system prompt from an AgentProfile. Includes agent name, role, disposition, backstory, and general behavioral instructions. This is the stable anchor that persists across all rounds.

`build_user_message` creates the user message with round context. Combines the agent-specific context (from agent.build_context) with round metadata like current round number and any pending notifications.

`format_tools` formats tool definitions for the Anthropic API. Ensures each tool has the correct schema with name, description, and input_schema.

`build_interview_turn` builds the prompt for a single interview turn. Includes the agent's system prompt, the interview context (role being discussed, who the other party is), and the conversation transcript so far.

## Extensibility for Future Agent Types

The abstract base class is designed with future expansion in mind. Adding new agent types (panel interviewers, technical screeners, coding challenge administrators) requires implementing the four abstract methods and nothing else.

Examples of future agent types:

**TechnicalScreenerAgent** -- administers coding challenges or system design exercises. Instead of a conversational interview, this agent presents a problem, evaluates the candidate's solution, asks follow-up questions, and scores technical ability. Tools would include present_problem, evaluate_solution, ask_followup, and score_candidate. Context would include a problem bank, difficulty calibration, and past scoring patterns.

**PanelCoordinator** -- extends the InterviewEngine for multi-interviewer panels. Manages turn-taking among multiple interviewers, each with their own evaluation criteria and question areas. The candidate interacts with several agents in a single session.

The interview engine already works against the BaseAgent interface, so new agent types plug in without modifying the engine. The simulation engine just needs to know when to schedule which type of interaction.

## Dependencies

Managed via uv with pyproject.toml. Core dependencies:

- anthropic -- API client for all LLM calls
- pydantic -- data models, validation, serialization
- psycopg (or asyncpg) -- Postgres driver
- httpx -- async HTTP client for Greenhouse API calls
- pyyaml -- config file parsing

Dev/analysis dependencies:

- jupyter -- post-run analysis notebooks
- matplotlib -- charting for blog post visuals
- streamlit (optional) -- interactive dashboard for exploring run data