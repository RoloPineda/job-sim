# job-sim

Welcome to job-sim. The goal of this project is to simulate the realities of today's tech job market and watch how AI agents deal with it.

The tech job market right now is defined by ghost jobs that were never meant to be filled, applications that disappear into the void, recruiter conversations that lead nowhere, and entry level roles that ask for at least 3+ years of experience. For the people navigating it, the whole process feels like a black box where getting a screen at all seems down to luck. And when a screen does come through, it's followed by multi-round interviews, leetcode problems, system design questions, and take-home assignments, each company with its own daunting process.

This project takes those exact conditions and drops AI agents into them to see what happens.

> **Status:** Active development. Not yet runnable end to end.


Every agent is autonomous. They have a name, a backstory, a personality, skills, and a savings account that drains every round. One of the first things they do is write their own resume based on what they believe about themselves, which varies in accuracy. Some agents are overconfident and some undersell themselves, and that shows up in the resume before anyone else even sees it.

From there, agents browse job postings, decide where to apply, write cover letters if they feel like it, and submit. Then they wait. Some companies respond quickly, some take weeks, and some never respond at all. Some of the postings are ghost jobs, reposted across multiple cities with identical descriptions or quietly relisted with a fresh date after expiring, and the agents have no way to tell which ones are real.

When a company does respond, the process mirrors real hiring. A recruiter agent screens the application and decides whether to forward it, writing up their own assessment of the candidate. A hiring manager agent reviews whoever the recruiter sends and their assessmenct, filtered through their own biases and preferences. Some hiring managers give clear feedback about what they want, some are vague, and some contradict themselves. The recruiter has to figure out what the hiring manager actually means and adjust accordingly.

If a candidate makes it far enough, they interview. The interview is an actual multi-turn conversation between two agents where the interviewer evaluates the candidate and the candidate evaluates the company. Both walk away with their own impression.

Every few rounds, agents step back and reflect on how things are going. These reflections feed back into the agent's context, which means the narrative an agent builds about its own experience shapes its future decisions. An agent that tells itself "nothing is working" will behave differently from one that tells itself "the market is tough but my approach is solid."

Meanwhile, savings keep draining. An agent with six months of runway behaves differently from one with six weeks, and that pressure shows up in which roles they apply to, how much effort they put into each application, and when they start considering things they wouldn't have looked at earlier.

## The questions

Some of the questions this simulation might answer are:

Do agents start cutting corners on applications after enough silence? Do they lower their standards gradually, in ways they might not acknowledge in their own reflections? Do they develop strategies for spotting ghost jobs, and are those strategies any good? Do some personality types hold up better than others under the same conditions? Does an agent that gets one encouraging response early on have a completely different trajectory from one that doesn't?

On the employer side, does a hiring manager who sees a streak of weak candidates start rejecting everyone out of pattern? Does a recruiter who gets vague feedback start guessing wrong about what the hiring manager wants? Does the friction between recruiter and hiring manager quietly filter out good candidates?

Nobody tells these agents how to behave. The market does.

## Documentation

See [`docs/`](docs/) for detailed writeups on how the system is built, starting with the [agent system](docs/agents.md).

## License

[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)