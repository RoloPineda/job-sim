# RunConfig

Stored once at the start of each simulation run. Makes runs reproducible and comparable.

For now this config assumes that we are using claude only. Might extend to other models later.

## Attributes:

### Model parameters:
These control which models are used and how creative their outputs are.

- Temperature: Controls how varied agent behavior is. Higher values produce more creative and unpredictable decisions, lower values make agents more consistent and deterministic. Worth experimenting with since this directly affects how "human" the agents feel.
- Top p: Works alongside temperature to control output diversity. Generally leave this close to 1.0 and use temperature as the primary knob.
- Sonnet model version: The model used for main agent decisions like applying to jobs, interviewing, negotiating, and reflecting. These are the high-stakes interactions where quality matters.
- Haiku model version: The model used for cheaper operations like history compression and summarization. Using a smaller model here keeps costs manageable without sacrificing quality on the interactions that matter.

### Context parameters:
These control how much history and context each agent carries in its prompt. The tradeoff across all three is cost vs. richness.

- Compression frequency: How often (in rounds) older events get compressed into a summary. Lower values mean more frequent compression which saves tokens but loses detail. Higher values preserve more raw history but risk hitting context limits.
- Recent history window: How many rounds of raw uncompressed events the agent sees in its prompt. This is the agent's short-term memory. Too small and the agent feels amnesic, too large, and we're burning tokens on events that don't matter anymore.
- Max context tokens: Hard ceiling on total tokens in the agent's prompt. Forces compression frequency and recent history window to stay in balance. If the assembled prompt exceeds this, something needs to get trimmed.

### Simulation structure parameters:
These define how rounds are organized and how agents interact within them.

- Turn structure: How a single round is organized. Defines the sequence of actions that happen within a round.
- Agent action order: The order in which agents take their turns each round. This matters because a seeker who acts before a recruiter reviews applications has a different experience than one who acts after.
- Reflection frequency: How often (in rounds) agents run a self-reflection prompt. More frequent reflections produce richer behavioral data but add cost.
- Interview turn floor: Minimum number of turns in an interview conversation. Prevents unrealistically short interviews.
- Interview turn ceiling: Maximum number of turns in an interview conversation. Prevents runaway conversations that burn tokens.

### Market parameters:
These shape the job market the seekers operate in. Different configurations let us study behavior under different market conditions.

- Market condition: Whether the market favors employers, employees, or is balanced. This gets fed into recruiter and HM prompts as context that shapes their behavior. In an employer-favored market, recruiters can afford to be pickier, take longer to respond, and ghost more freely because they know there's a deep candidate pool. HMs can hold out for a perfect fit instead of settling. In an employee-favored market, companies need to move fast, offer competitive comp, and treat candidates well or risk losing them. Seekers feel this indirectly through how those agents treat them rather than through any direct mechanical effect.
- Ghost job percentage: What percentage of postings are ghost jobs that never advance candidates. Higher values create a more frustrating market for seekers. At seeding, this determines how many postings get is_ghost = True on the JobPosting. At runtime, applications to ghost postings should never advance regardless of how the recruiter or HM would normally behave. That's engine logic. The seeker can't distinguish a ghost posting from a real one where the company just ghosts them (responsiveness_pattern = "ghosts" on CompanyProfile). Both feel the same to the seeker, but the causes are different. For recruiters, being assigned a ghost posting means screening candidates for a role that will never be filled, which could create interesting friction with the HM over time. 
- Rejection specificity: How much detail (low, moderate, high) companies give when rejecting candidates. Some markets give detailed feedback, others send generic rejections or nothing at all. This feeds into how the recruiter and HM agents construct their rejection messages. High specificity means the seeker gets actionable feedback they can use to adjust their approach, rewrite their resume, or shift their target roles. Low specificity means the seeker is left guessing, which makes it harder for the LLM to course-correct the agent's strategy. This interacts with the HM's feedback_clarity since a vague HM in a low-specificity market gives the seeker almost nothing to work with.
- New postings per round: How many new jobs appear on the board each round. Controls whether the market feels stagnant or active. At runtime, the JobBoard publishes this many new postings each round. A high value gives seekers fresh opportunities to evaluate and apply to, keeping the search feeling dynamic. A low value means the same stale postings sit on the board, and seekers who've already applied to everything relevant have nothing to do but wait. It also affects recruiter workload since more postings mean more applications to screen.
- Posting expiry rounds: How many rounds a posting stays active before expiring. Short expiry creates urgency for seekers to apply quickly and means the board turns over faster. Long expiry means more options accumulate but some of those postings may be stale or effectively dead even if not technically expired. At runtime, the JobBoard checks each posting's round_posted plus this value against the current round and closes expired ones. This interacts with new_postings_per_round to determine the total number of active postings at any given time. For seekers, expired postings they were tracking or planning to apply to create a sense of missed opportunity.

### Scale parameters:
These control the size of the simulation.

- Num seekers: Total number of jobseeker agents.
- Num companies: Total number of companies.
- Num postings: Total number of initial job postings seeded at the start.
- Total rounds: How many rounds the simulation runs. Combined with what a round represents, this determines the total simulated time period.