# Company classes


## CompanyProfile
Keeping this immutable for now. Companies are unlikely to change their hiring behaviors during a period of 3-6 months unless major events happen.
- Id: Unique identifier for the company.
- Name: Company name.
- Industry: What sector the company operates in. Using literal to prevent situations like "tech", "Tech", "technology"
- Size: Scale of the company. Keeping it as string since saying "startup" signals behavior better than having a number and then having to map that to a category. 
- Growth stage: Where the company is in its lifecycle (early, scaling, mature, etc.). A scaling company hires aggressively while a mature one is more selective. 
- Culture description: Freeform text describing the company's culture and values. This gets fed into recruiter and HM prompts to shape how they evaluate candidates and communicate. 
- Budget flexibility: How much room the company has to negotiate on comp (rigid, moderate, flexible). A rigid company won't budge on salary while a flexible one might stretch for the right candidate. 
- Responsiveness pattern: How the company typically responds to candidates (fast, slow, unpredictable, ghosts). This is a major driver of candidate experience. Ghosting is one of the most common and frustrating patterns in real job searches. 
- Base response delay: Number of rounds before the company typically responds. This is a fixed trait set at seeding that reflects the company's general speed. A fast company might have a base of 1, a slow company might have a base of 5. The actual delay for any specific interaction is computed at runtime by the simulation engine using this value combined with response delay variance. Minimum of 1 since a company can't respond in zero rounds. 
- Response delay variance: Int representing the range of randomness added to base response delay. At runtime, the engine computes the actual delay as base_response_delay plus or minus up to this value (clamped to at least 1). For example, a company with base 3 and variance 2 would respond anywhere between 1 and 5 rounds for any given interaction. This is not randomized at seeding. It's a fixed property of the company that tells the engine how predictable or unpredictable this company's response times are. Minimum of 0 for companies with consistent timing. Must be less than base_response_delay to avoid computing negative delays.

---

## JobPosting:

- Id: Unique identifier for the posting. 
- Company id: Which company this posting belongs to. 
- Hiring manager id: Which hiring manager owns this role. Direct link so the simulation doesn't have to traverse through recruiters to find who interviews candidates. 
- Title: Job title (e.g., "Senior Backend Engineer"). 
- Department: Which team or org the role sits in. 
- Description: Freeform job description the seeker sees when browsing. 
- Requirements: List of stated requirements for the role. These are what the seeker evaluates themselves against when deciding whether to apply. 
- Salary range low: Should be int and the yearly dollar amount. Bottom of the posted salary range, or None if the company doesn't disclose. 
- Salary range high: Should be int and the yearly dollar amount. Top of the posted salary range, or None if the company doesn't disclose. 
- Location: Where the role is based. 
- Remote: Whether the role is remote. 
- Seniority: Level of the role (junior, mid, senior, lead, staff). 
- Posted round: The simulation round when this job was listed on the board. What a round represents (day, week, month) is defined in RunConfig. Combined with the current round, this tells us how long the posting has been open.
- Expiry round: The simulation round when this posting comes off the board, or None if it stays up indefinitely. The simulation automatically closes expired postings and rejects any pending applications.
- Status: Current state of the posting (open, closed, filled, expired). Mutable since this changes as the simulation progresses. 
- Is ghost: Hidden flag. If true, the posting accepts applications but never advances anyone. The seeker has no way to know this. This is a real and common phenomenon. Companies post roles they have no intention of filling, sometimes for headcount planning, sometimes because the role is already filled internally, sometimes just to build a talent pipeline. 
- Actual budget: Hidden field. The real budget the company has for this role, which may differ from the posted range. Used by the simulation to evaluate offers and negotiations.