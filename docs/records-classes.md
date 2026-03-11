
## ApplicationRecord

- Id: Unique identifier for this application.
- Seeker id: Which jobseeker submitted the application.
- Posting id: Which posting they applied to.
- Recruiter id: Which recruiter is responsible for reviewing this application. Makes it easier to trace who handled what without having to look up the posting's assigned recruiter.
- Resume version id: Which version of the resume was used for this application.
- Cover letter version id: Which cover letter was submitted, or None if the seeker didn't write one.
- Round submitted: The simulation round when the application was sent.
- Status: Current state of the application (pending, reviewed, rejected, advanced, ghosted). Ghosted is distinct from rejected since the seeker never gets a response to a ghosted application.
- Status updated round: The round when the status last changed, or None if still pending. Combined with round_submitted this tells us how long the seeker waited for a response, which is itself useful behavioral data.

--- 

## ResumeVersion

- Id: Unique identifier for this resume version.
- Seeker id: Which jobseeker wrote this resume.
- Round created: The simulation round when this version was written.
- Full text: The complete resume text.
- Trigger: What caused the rewrite (initial, general_rewrite, tailored). Initial is the starting resume. General rewrite means the agent decided to overhaul without a specific posting in mind. Tailored means they customized for a specific role.
- Target posting id: The posting this resume was tailored for, or None if the rewrite wasn't targeting a specific role. Initial and general_rewrite won't have a target. Tailored might.
- State summary at creation: Freeform string summarizing the agent's state when they wrote this version. Something like "round 12, 8 rejections, $4000 savings remaining." Captures context for understanding what drove the rewrite without duplicating the full AgentState snapshot that's already stored separately each round.

## CoverLetterVersion

- ID: Unique identifier for this cover letter version.
- Seeker id: Which jobseeker wrote this cover letter.
- Round created: The simulation round when this was written.
- Full text: The complete cover letter text.
- Trigger: What caused the write (initial, tailored). Simpler than resume triggers since cover letters are almost always written for a specific posting. There's no "general rewrite" equivalent.
- Target posting id: The posting this cover letter was written for. Unlike ResumeVersion this is required since cover letters are always tied to a specific application.
- State summary at creation: Same as ResumeVersion. Freeform string summarizing the agent's state at time of writing for behavioral context.

---

## ReflectionInterviewRecord

- ID: Unique identifier for this interview.
- Application id: Links back to the application that led to this interview. From there we can trace the full chain back to the seeker, posting, and resume used.
- Interviewer id: Who conducted the interview. Could be a recruiter or hiring manager.
- Interviewer type: Whether the interviewer is a recruiter or hiring manager. This matters because the nature of the interview differs. A recruiter interview is typically a phone screen or culture fit check, while a hiring manager interview is usually technical or role-specific.
- Round scheduled: The simulation round when the interview was booked. The gap between this and round_conducted shows how long the candidate waited, which is data about how fast the company moves and affects candidate experience. 
- Round conducted: The simulation round when the interview actually took place.
- Transcript: Stored as a JSON column in Postgres. List of speaker/content dicts capturing the full conversation. Array order is preserved by Postgres so the transcript reads back in sequence. Gets populated turn by turn as the simulation engine alternates between the interviewer and candidate agents. Each turn, one agent speaks and the other responds, with the engine passing each message back and forth until the interview concludes. The number of turns is bounded by interview_turn_floor and interview_turn_ceiling in RunConfig.
- Interviewer evaluation: Optional freeform text. After the interview transcript is complete, the interviewer agent is prompted separately to evaluate the candidate. This is independent of the candidate's evaluation so neither side influences the other. Optional because a slow or disengaged interviewer might not produce one.
- Candidate evaluation: Optional freeform text. Same mechanism as interviewer evaluation but from the candidate's perspective. The agent is prompted to reflect on how the interview went, how they felt about the role and interviewer, and whether they'd want to move forward. This feeds into the seeker's decision-making in future rounds.
- Outcome: Result of the interview (advanced, rejected, undecided). Ghosting is not included here since that's handled at the application level. If an interview happened, there was engagement. The silence comes afterward if the company never follows up, which ApplicationRecord captures.

---

## OfferRecord

- ID: Unique identifier for this offer.
- Application id: Links back to the full application chain.
- Round extended: The simulation round when the offer was made.
- Base salary: The core compensation number being negotiated. In dollars. Int.
- Total comp: Optional int representing the full package value when calculable.
- Negotiation history: Stored as a JSON column in Postgres. List of dicts capturing each back-and-forth move. Each entry includes the round, which party made the move, the proposed amount, and their reasoning. The reasoning is LLM-generated and captures how the agent justifies its position, which is behavioral data I think could yield interesting insights.
- Final outcome: Current state of the offer (accepted, declined, negotiating).
- Round resolved: The round when the offer was accepted or declined, or None if still negotiating. Combined with round_extended this shows how long the negotiation took.
- Additional benefits: Optional freeform text covering equity, bonus, signing bonus, relocation, or anything else beyond base. Not structured since negotiation logic focuses on base salary for now. Plan to break this out into structured fields later if agents start making interesting tradeoffs between comp components.

--- 

## RecruiterHMMessage

- ID: Unique identifier for this message.
- Sender id: Who sent the message. Could be the recruiter or the hiring manager.
- Receiver id: Who received the message.
- Round: The simulation round when the message was sent.
- Content: Freeform text generated by the LLM. This is where behavioral data lives. How a recruiter frames a candidate to the HM, how the HM gives feedback, whether the recruiter pushes back on unrealistic requirements. All captured here.
- Message type: The purpose of the message (candidate_forward, feedback, nudge, role_change_request). Candidate forward is the recruiter presenting a candidate. Feedback is the HM responding with their take. Nudge is the recruiter pushing the HM to move faster on a decision. Role change request is the recruiter suggesting the requirements need adjusting because they can't find matching candidates.
- Posting id: Which posting this message relates to. Most communication between recruiter and HM is in the context of a specific role.
- Related application id: Which application this message is about, or None if the message is about the role in general rather than a specific candidate. A nudge or role_change_request might not reference a particular application.

--- 
## StateSnapshot
This is the primary data source for tracking behavioral progression over time. You can pull an agent's snapshots in order and see exactly how their state evolved round by round.

- Id: Unique identifier for this snapshot. 
- Agent id: Which agent this snapshot belongs to. 
- Agent type: What kind of agent (job_seeker, recruiter, hiring_manager). Included here so we can filter snapshots by agent type without joining back to the agent profile. 
- Round number: Which simulation round this snapshot was taken at. 
- State JSON: Serialized AgentState as a dict. This is the complete mutable state at that point in time. Written at the end of every round for every agent. 
- Created at: Timestamp when the snapshot was saved. Useful for debugging and ordering even though round_number already provides logical ordering.

--- 
## ReflectionEntry:

- Id: Unique identifier for this reflection. 
- Agent id: Which agent produced this reflection. 
- Agent type: What kind of agent. Same reasoning as StateSnapshot for filtering convenience. 
- Round number: Which simulation round this reflection was generated at. 
- Prompt used: The full reflection prompt that was sent to the LLM. Captured so we can understand what the agent was asked and reproduce the reflection if needed. 
- Response: The LLM's response. This is the agent's self-assessment in its own words. Things like how they think the search is going, what they might change, whether they're feeling discouraged. 
- Context summary: Summary of the agent's state that was active when the reflection was generated. Similar to state_summary_at_creation on ResumeVersion. Gives the context that shaped the reflection without needing to cross-reference the full state snapshot.

---
## EventEntry:

- ID: Unique identifier for this event. 
- Agent id: Which agent this event relates to, or None for system-level events that aren't tied to a specific agent (like a posting expiring). 
- Round number: Which simulation round this event occurred in. 
- Event type: What happened. This is a catch-all covering things like application_submitted, rejection_sent, interview_scheduled, offer_extended, posting_closed, resume_updated, tool_called, and anything else that occurs during the simulation. 
- Details: Dict containing event-specific data. Structure varies by event type. An application_submitted event might include the posting_id and resume_version_id, while a rejection_sent event might include the application_id and reason. 
- Created at: Timestamp for ordering and debugging.