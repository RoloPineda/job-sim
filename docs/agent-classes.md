# Class attributes

This is an ongoing journal of decisions and reasoning behind the decisions being made surrounding class attributes.

## AgentProfile class 
This is the shared identity that all agent types inherit from. This contains only the attributes that every agent in the simulation needs regardless of whether they're a jobseeker, recruiter, or hiring manager.

### Attributes:

- Id: Unique identifier for the agent.
- Agent type: What kind of agent this is (job_seeker, recruiter, hiring_manager).
- Name: The agent's name (first and last name)
- Disposition: I envision this as behavioral's tendencies in how they act. Essentially personality traits that shape decision-making. Examples would be anxious and risk-averse, or cautious and methodical. The idea is that this gives the LLM more of a personality and allow us to create different types of agents. Another example would be "thorough and empathetic" for a recruiter who carefully evaluates candidates, or "overworked and checkbox-oriented" for one who rushes through screening.
- Backstory: The narrative context for who this agent is and how they got here. For a hiring manager this could be something like "burned by a bad hire last quarter, now overly cautious with candidates." Combined with disposition this gives the LLM enough to produce differentiated behavior across agents of the same type.
  - Disposition and backstory are kept separate to make seeding easier. We can mix and match to create more variety without writing unique combinations for every agent.
- Location: Where the agent is based. For jobseekers this is where they live. For recruiters and hiring managers this could influence biases toward local vs. remote candidates.

## Jobseeker class
The goal of this class is to simulate a real jobseeker, therefore, we need to capture the right profile. Jobseekers have certain categories of attributes that would be helpful in our simulation:

1. Identity:

This tells us who the jobseeker is, the background, and experience. Each agent begins with an identity that we will seed.

- Education: Should this be its own class since it has School, Degree, Year
- Actual skills: Ground truth the simulation uses. Things like Python, SQL, etc.
- Experience years: Int that shows experience. I keep it as a separate number from work history because we might have cases such that an agent has been in the workforce for 10+ years but only 3 of those are relevant for the role. The tradeoff here is that we might run into consistency issues.
- Work History: Companies worked for, titles held, dates worked there and bullets. 
  * Should be a class

2. Self-perception:

Keeping this immutable for now, since make these mutable would introduce things like learning from interview feedback, etc.
- Perceived skills: This is what the agent believes its good at which may or may not match its actual skills.
- Self-awareness level: Whether the agent is accurate, overconfident, or underconfident. This drives the gap between perceived and actual skills. An overconfident agent might apply to roles way above their level or confidently talk about things they don't deeply understand in interviews. An underconfident agent might skip roles they're qualified for or undersell in negotiations.
- Communication ability: This might include something like strong, average, or weak. This affects how well the agent performs during interviews and presents itself in applications. For example, a strong communicator might speak eloquently during interviews and craft good resumes. A weak communicator might undersell even if they have good skills and self-awareness.

3. Preferences

Most of these are mutable fields that will evolve overtime.
- Target roles: The roles the agent is going after. Could be one or multiple. For example AI/ML engineer, SWE, etc. Mutable since I want to observe how these preferences change.
- Target seniority: The level the agent is targeting (junior, mid, senior, lead, and so on). This when combined with self-awareness could be interesting because we could see overconfident agents applying for senior roles. Mutable since the agent might start applying to lower seniority levels out of desperation.
- Target comp low: The floor the agent would generally accept. Below this they walk away. I am interested in seeing how this changes as financial pressure and unemployed time affects the agent. 
- Target comp high: The ideal comp for this agent. This is what they'd ask in a negotiation if they felt like they had leverage. The gap between low/high shows how much room for negotiation is there.
- Location flexibility: How willing is the agent to relocate (rigid, moderate, flexible). A rigid agent only considers job in their current location, a flexible one is open to moving, a moderate might move if the comp is good. This is mutable because I want to see how this changes overtime with financial pressure.
- Remote preference: Whether the agent prefers remote, hybrid or on-site. An agent with rigid location but a strong remote preference could apply to a remote job that comes from a different location. Also mutable.

4. Financial:

- Savings: The dollar amount the agent has in savings. The idea is that this will decrease each round to simulate what a real unemployed person encounters in the real world and put more pressure on the agent.
- Burn rate: How much the agent spends per round. Round intervals can represent different timelines (daily, weekly, monthly) and this should be defined in the simulation config so that the burn rate is relative to that.

5. Runtime state:

Current pipeline
Current resume
Recent events
Compressed history
Metrics (application count, rejection rate, etc.)
Last reflection
Round number

Derived/implicit (no need to store, can be inferred):

Unemployed time (current round minus round the agent started searching)
Morale/urgency (inferred from behavior, as you said)
---

## RecruiterProfile 
Extends AgentProfile. The recruiter is the middleman between jobseekers and hiring managers. They screen candidates, forward the promising ones, and manage communication between both sides.

### Attributes:

- Company id: Which company this recruiter works for. This links them to the company's behavioral tendencies.
- Assigned posting ids: Which job postings this recruiter is responsible for. This is their scope. They only screen and manage candidates for these roles.
- Hiring manager ids: Which hiring managers this recruiter works with. A recruiter might manage postings across multiple HMs.
- Experience level: Junior, mid, or senior. This affects how well they screen candidates, how they frame candidates to hiring managers, and how much autonomy they take. A junior recruiter might forward borderline candidates for the HM to decide while a senior one filters more aggressively.
- Current workload: Number of open roles they're managing. A recruiter juggling 15 roles behaves differently from one focused on 3. They might influence things like rush screening, send more templated responses, or deprioritize lower-priority postings.

---

## HiringManagerProfile 
Extends AgentProfile. The hiring manager is the final decision-maker on candidates. They set the bar, conduct interviews, and decide on offers.

### Attributes:

- Company id: Which company this hiring manager belongs to.
- Team size: How big their current team is.
- Team situation: The state of their team (understaffed, stable, growing, rebuilding). An understaffed HM feels urgency to hire while a stable one can afford to be picky.
- Management style: How they interact with candidates and recruiters. This shapes interview dynamics and how useful their feedback is to recruiters.
- Technical bar: How demanding a hiring manger is. The idea is to capture the preferences of the hiring manager. For example, one might say the technical bar is "needs deep expertise in working at scale, strong at low level system design, and devops" while another one might say "solid fundamentals".
- Interview capacity per round: How many interviews they can do in a given round. This is to capture the realities of a HM a busy HM. Might observe delay in interviews, which affects candidate experience and pipeline speed.
- Past hiring description: Context about their previous hires and experiences. Something like "last three hires were all senior engineers from big tech, tends to favor that background." Gives the LLM implicit biases to work with.
- Feedback clarity: How clearly the HM communicates what they want to the recruiter (clear, vague, contradictory). A vague HM rejects candidates without useful reasoning, leaving the recruiter guessing about what to screen for. A contradictory one says they want one thing but keeps picking the opposite. It introduces real misalignment that affects the candidate experience.