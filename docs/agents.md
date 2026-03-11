# Agents

Agents are autonomous LLM-backed participants in the simulation. Each agent has a fixed identity (profile), evolving per-round state, and a set of tools it can invoke to take actions. The LLM sees a system prompt built from the agent's profile and current context, makes decisions through tool calls, and produces side effects that the engine persists after the turn ends.

There are three agent types: jobseekers, recruiters, and hiring managers. Together they form the core interaction loop of the simulation: jobseekers apply to postings, recruiters screen and forward candidates, and hiring managers make final decisions.


## Architecture

All agents inherit from `BaseAgent`, which provides the API call loop, retry/backoff logic, soft cap enforcement, and usage tracking. Subclasses implement four abstract methods:

- `get_tools()` returns tool definitions for the Anthropic API.
- `build_context()` assembles the agent's current situation into a string injected as the user message.
- `handle_tool_call(tool_name, tool_input)` dispatches a tool invocation to the appropriate handler.
- `evaluate(interaction)` produces a structured assessment after an interaction (e.g., post-interview).

Each agent type has its own profile and state class:

| Agent             | Profile                | State                | Tools                    |
|-------------------|------------------------|----------------------|--------------------------|
| `JobSeekerAgent`  | `JobSeekerProfile`     | `JobSeekerState`     | `job_seeker_tools()`     |
| `RecruiterAgent`  | `RecruiterProfile`     | `RecruiterState`     | `recruiter_tools()`      |
| `HiringManagerAgent` | `HiringManagerProfile` | `HiringManagerState` | `hiring_manager_tools()` |


## Profile and State

**Profiles** are frozen Pydantic models representing an agent's identity: name, disposition, backstory, skills, company assignment, and other traits that don't change during a simulation. All profile classes inherit `frozen=True` from `AgentProfile`.

**States** are mutable Pydantic models representing everything that changes round to round. Each agent type has a typed state subclass (`JobSeekerState`, `RecruiterState`, `HiringManagerState`) with explicit fields instead of a generic dict, which prevents key typos and gives IDE support.

The ORM layer stores seeded starting values as queryable columns on the agent tables. The live state is serialized to the `Agent.state` JSONB column at the end of each round. On the first round, the engine hydrates the state from the ORM columns. On subsequent rounds, it deserializes from the JSONB.

Shared value objects (`Education`, `WorkEntry`) live in `schemas/shared.py` and are used by profiles but have no independent identity.


## Turn Lifecycle

A turn is one agent's complete action sequence within a round. The engine calls `agent.run_turn(round_number, notifications)`, which:

1. Calls `build_context()` to assemble what the agent currently knows.
2. Passes the context through `PromptBuilder` to construct the system prompt and user message.
3. Calls the Anthropic API with the agent's tool definitions.
4. Extracts tool-use blocks from the response. If there are none, the turn ends.
5. Executes each tool call via `handle_tool_call()`, collecting results.
6. Appends the assistant response and tool results to the conversation, then loops back to step 3.

The turn ends when the model stops making tool calls, or when the soft cap is reached.

### Soft Cap

The soft cap limits how many tool calls an agent can make in a single turn. When the cap is reached, a nudge message is appended to the last tool result telling the agent it has one more action. The agent gets one final API exchange, then the turn ends regardless. What the agent chooses to do with its last action is behavioral data.

The nudge rides on the last tool result rather than as a separate message because the API requires strict user/assistant alternation.

### Error Handling

If a tool call raises an exception, the error is returned to the model as an `is_error` tool result rather than crashing the turn. The model can retry or move on. If the API call itself fails after retries, the turn is skipped and the `TurnResult` records the reason.


## Agent Types

### JobSeeker

Represents a person searching for a job. Browses postings, writes and rewrites resumes, submits applications, and eventually interviews and evaluates offers. Makes autonomous decisions about where to apply, how much effort to invest in each application, and how selective to be.

Financial pressure is a key behavioral driver. `JobSeekerState` tracks `savings` and `burn_rate`, and the context prompt shows the agent its estimated runway. As savings deplete, agents may lower their standards, apply more broadly, or accept offers they would have negotiated earlier.

The agent never sees hidden posting fields like `is_ghost` or `actual_budget`. It sees the same information a real candidate would see.

**Side effects produced per turn:**
- `resume_versions`: New resume versions (append-only, each write creates a new record).
- `applications`: Applications submitted to postings.

### Recruiter

Operates as the bridge between jobseekers and hiring managers. Screens incoming applications, forwards promising candidates with a written assessment, sends status updates and rejections to candidates, and nudges unresponsive hiring managers.

The recruiter sees candidate resumes, posting requirements, and the history of messages exchanged with hiring managers. How it frames a candidate to the hiring manager is itself behavioral data worth analyzing.

**Side effects produced per turn:**
- `hm_messages_sent`: Messages to hiring managers (forwards, nudges).
- `events_created`: Status notifications directed at jobseekers (rejections, advances).

### Hiring Manager

The final decision-maker on candidates. Reviews forwarded candidates, provides feedback to recruiters on pipeline quality, and rejects candidates with reasoning that flows back to the recruiter. The recruiter's framing is visible alongside the candidate's resume, but the HM forms its own opinion.

The hiring manager's `feedback_clarity` trait (clear, vague, contradictory) affects how useful its feedback is to the recruiter, which in turn affects screening quality over time. A vague HM forces the recruiter to guess at preferences, while a contradictory one actively degrades pipeline calibration.

Interview capacity is bounded per round by `interview_capacity_per_round`. Nudges from recruiters are surfaced in the context to create social pressure toward timely decisions.

**Side effects produced per turn:**
- `hm_messages_sent`: Feedback messages to recruiters (pipeline quality, rejection reasoning).
- `events_created`: Rejection notifications directed at jobseekers.


## Engine Contract

The engine is responsible for constructing agents, running turns, and persisting results. The agent is not responsible for any persistence or cross-agent communication routing.

### What the engine provides at construction

Each agent receives pre-fetched data relevant to its role:

- **Jobseekers** get visible postings. They have no knowledge of which recruiter manages which posting.
- **Recruiters** get their assigned postings, pending applications, hiring manager message history, and seeker info (name and resume for each applicant).
- **Hiring managers** get their managed postings, forwarded applications, the full recruiter message history (forwards, nudges, and their own prior feedback), seeker info for forwarded candidates, and a recruiter name map for addressing feedback.

### What the engine collects after a turn

The engine reads the side effect lists from the agent instance (`resume_versions`, `applications`, `hm_messages_sent`, `events_created`) and persists them. It also serializes the updated state back to the JSONB column.

The engine fills in `recruiter_id` on jobseeker-submitted applications before persisting, since jobseekers don't have visibility into recruiter assignments.

Status mutations on in-memory records (e.g., setting `app.status = "reviewed"` during a forward) happen on the objects passed to the agent at construction. The engine must persist these changes.


## Tool Definitions

All tool schemas live in `tools/definitions.py`. Each agent type has an assembly function (`job_seeker_tools()`, `recruiter_tools()`, `hiring_manager_tools()`) that returns a deep copy of the relevant tool definitions. The deep copy prevents any in-memory mutation from corrupting the module-level definitions.

Tool name constants are defined alongside the schemas and imported by the agent classes for use in handler dispatch.

Tools that are defined but not yet implemented return a generic stub message. The model sees the full tool set so its planning accounts for capabilities that will exist later, but invoking a stubbed tool has no effect.