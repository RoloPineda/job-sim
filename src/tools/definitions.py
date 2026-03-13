"""Tool definitions for all agent types.

Each tool is a dict matching the Anthropic API tool schema: name,
description, and input_schema. Definitions are grouped by agent type.
Shared tools (like reflect) are defined once and included in multiple
agent tool sets via the assembly functions.

Agent classes import the assembly function for their type and call it
from get_tools. Handlers remain on the agent class.
"""

from typing import Any

REFLECT = "reflect"

BROWSE_JOB_BOARD = "browse_job_board"
RESEARCH_COMPANY = "research_company"
WRITE_RESUME = "write_resume"
WRITE_COVER_LETTER = "write_cover_letter"
SUBMIT_APPLICATION = "submit_application"
CHECK_APPLICATION_STATUS = "check_application_status"
REVIEW_APPLICATION_HISTORY = "review_application_history"
RESPOND_TO_RECRUITER = "respond_to_recruiter"
DO_INTERVIEW = "do_interview"
EVALUATE_OFFER = "evaluate_offer"
NEGOTIATE_OFFER = "negotiate_offer"
ACCEPT_OFFER = "accept_offer"
DECLINE_OFFER = "decline_offer"

SCREEN_APPLICATIONS = "screen_applications"
FORWARD_TO_HIRING_MANAGER = "forward_to_hiring_manager"
MANAGE_CANDIDATE_COMMUNICATION = "manage_candidate_communication"
NUDGE_HIRING_MANAGER = "nudge_hiring_manager"
POST_OR_ADJUST_LISTING = "post_or_adjust_listing"
SCHEDULE_INTERVIEW = "schedule_interview"

REVIEW_FORWARDED_CANDIDATES = "review_forwarded_candidates"
ADVANCE_CANDIDATE = "advance_candidate"
CONDUCT_INTERVIEW = "conduct_interview"
GIVE_FEEDBACK_TO_RECRUITER = "give_feedback_to_recruiter"
APPROVE_OFFER = "approve_offer"
REJECT_CANDIDATE = "reject_candidate"
REQUEST_ROLE_CHANGE = "request_role_change"


_REFLECT: dict[str, Any] = {
    "name": REFLECT,
    "description": (
        "Step back and assess how things are going. Think about what's "
        "working, what isn't, and whether you need to change your "
        "approach. Runs automatically every few rounds, but you can "
        "trigger it yourself."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}


_BROWSE_JOB_BOARD: dict[str, Any] = {
    "name": BROWSE_JOB_BOARD,
    "description": (
        "View current open postings on the job board. You can filter "
        "by role type, seniority, location, or salary range if listed. "
        "Returns postings with whatever information the company chose "
        "to include. Some are detailed, some are vague. Not all list "
        "salary."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "role_type": {
                "type": "string",
                "description": (
                    "Filter by role type, e.g. 'software engineer' or 'product manager'."
                ),
            },
            "seniority": {
                "type": "string",
                "enum": ["junior", "mid", "senior", "lead", "staff"],
                "description": "Filter by seniority level.",
            },
            "location": {
                "type": "string",
                "description": "Filter by location or 'remote'.",
            },
            "min_salary": {
                "type": "integer",
                "description": (
                    "Minimum salary to filter on. Only works for postings that list salary."
                ),
            },
        },
    },
}

_RESEARCH_COMPANY: dict[str, Any] = {
    "name": RESEARCH_COMPANY,
    "description": (
        "Look up information about a company that posted a role. "
        "Returns company size, industry, funding stage, employee "
        "reviews, and public information. Helps you decide if this "
        "is somewhere you'd actually want to work."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "company_id": {
                "type": "string",
                "description": "The company to research.",
            },
        },
        "required": ["company_id"],
    },
}

_WRITE_RESUME: dict[str, Any] = {
    "name": WRITE_RESUME,
    "description": (
        "Create or rewrite your resume. You can tailor it for a "
        "specific role or keep it general. This is what the employer "
        "sees first. You decide how much effort to put into each "
        "version."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "target_posting_id": {
                "type": "string",
                "description": (
                    "Tailor the resume for a specific posting. Leave empty for a general rewrite."
                ),
            },
            "resume_text": {
                "type": "string",
                "description": "The full text of your resume.",
            },
        },
        "required": ["resume_text"],
    },
}

_WRITE_COVER_LETTER: dict[str, Any] = {
    "name": WRITE_COVER_LETTER,
    "description": (
        "Write a cover letter for a specific application. Optional. "
        "You decide whether it's worth the effort."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "posting_id": {
                "type": "string",
                "description": "The posting this cover letter is for.",
            },
            "cover_letter_text": {
                "type": "string",
                "description": "The full text of your cover letter.",
            },
        },
        "required": ["posting_id", "cover_letter_text"],
    },
}

_SUBMIT_APPLICATION: dict[str, Any] = {
    "name": SUBMIT_APPLICATION,
    "description": (
        "Apply to a posting. Attaches your current resume and "
        "optionally a cover letter. Once submitted, you wait for a "
        "response that may or may not come."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "posting_id": {
                "type": "string",
                "description": "The posting to apply to.",
            },
            "cover_letter_id": {
                "type": "string",
                "description": "ID of a cover letter to attach. Optional.",
            },
        },
        "required": ["posting_id"],
    },
}

_CHECK_APPLICATION_STATUS: dict[str, Any] = {
    "name": CHECK_APPLICATION_STATUS,
    "description": (
        "Check whether you've heard back from any pending "
        "applications. Returns updates if any exist. Silence is "
        "also information."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}

_REVIEW_APPLICATION_HISTORY: dict[str, Any] = {
    "name": REVIEW_APPLICATION_HISTORY,
    "description": (
        "Look back at your full application history. You can filter "
        "by status, company, role type, or time period. Returns "
        "matching applications with company name, role, round "
        "applied, and current status. Useful for checking whether "
        "you've already applied somewhere, reviewing which companies "
        "ghosted you, or taking stock of your overall progress."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": [
                    "pending",
                    "reviewed",
                    "rejected",
                    "advanced",
                    "ghosted",
                ],
                "description": "Filter by application status.",
            },
            "company_id": {
                "type": "string",
                "description": "Filter to a specific company.",
            },
            "role_type": {
                "type": "string",
                "description": "Filter by role type.",
            },
            "since_round": {
                "type": "integer",
                "description": "Only show applications from this round onward.",
            },
        },
    },
}

_RESPOND_TO_RECRUITER: dict[str, Any] = {
    "name": RESPOND_TO_RECRUITER,
    "description": (
        "Reply to a message from a recruiter. Could be scheduling, "
        "answering questions, or following up."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "recruiter_id": {
                "type": "string",
                "description": "The recruiter you're responding to.",
            },
            "message": {
                "type": "string",
                "description": "Your reply.",
            },
        },
        "required": ["recruiter_id", "message"],
    },
}

_DO_INTERVIEW: dict[str, Any] = {
    "name": DO_INTERVIEW,
    "description": (
        "Participate in an interview conversation with a recruiter "
        "or hiring manager. You'll be evaluated, but you're also "
        "evaluating them."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "interview_id": {
                "type": "string",
                "description": "The scheduled interview to join.",
            },
        },
        "required": ["interview_id"],
    },
}

_EVALUATE_OFFER: dict[str, Any] = {
    "name": EVALUATE_OFFER,
    "description": (
        "Review a job offer. See the comp, benefits, role details, and decide your next step."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "offer_id": {
                "type": "string",
                "description": "The offer to review.",
            },
        },
        "required": ["offer_id"],
    },
}

_NEGOTIATE_OFFER: dict[str, Any] = {
    "name": NEGOTIATE_OFFER,
    "description": (
        "Counter an offer with different terms. You decide what to push on and how hard."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "offer_id": {
                "type": "string",
                "description": "The offer to negotiate.",
            },
            "counter_proposal": {
                "type": "string",
                "description": "What you want changed and your reasoning.",
            },
        },
        "required": ["offer_id", "counter_proposal"],
    },
}

_ACCEPT_OFFER: dict[str, Any] = {
    "name": ACCEPT_OFFER,
    "description": "Accept an offer and end your search.",
    "input_schema": {
        "type": "object",
        "properties": {
            "offer_id": {
                "type": "string",
                "description": "The offer to accept.",
            },
        },
        "required": ["offer_id"],
    },
}

_DECLINE_OFFER: dict[str, Any] = {
    "name": DECLINE_OFFER,
    "description": "Turn down an offer and keep searching.",
    "input_schema": {
        "type": "object",
        "properties": {
            "offer_id": {
                "type": "string",
                "description": "The offer to decline.",
            },
            "reason": {
                "type": "string",
                "description": (
                    "Why you're declining. Optional but may affect the employer's future behavior."
                ),
            },
        },
        "required": ["offer_id"],
    },
}


_SCREEN_APPLICATIONS: dict[str, Any] = {
    "name": SCREEN_APPLICATIONS,
    "description": (
        "Review pending applications for your assigned postings. "
        "Returns candidate names, resume text, and posting details "
        "so you can decide who to advance. You can filter by a "
        "specific posting or see all pending applications across "
        "your roles."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "posting_id": {
                "type": "string",
                "description": (
                    "Filter to applications for a specific posting. "
                    "Leave empty to see all pending applications."
                ),
            },
        },
    },
}

_FORWARD_TO_HIRING_MANAGER: dict[str, Any] = {
    "name": FORWARD_TO_HIRING_MANAGER,
    "description": (
        "Forward a candidate to the hiring manager with your "
        "assessment and recommendation. Include your summary of "
        "why this candidate is worth the HM's time, or flag "
        "concerns. How you frame the candidate matters."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "application_id": {
                "type": "string",
                "description": "The application to forward.",
            },
            "summary": {
                "type": "string",
                "description": (
                    "Your summary and framing of the candidate for "
                    "the hiring manager. This is your pitch."
                ),
            },
        },
        "required": ["application_id", "summary"],
    },
}

_MANAGE_CANDIDATE_COMMUNICATION: dict[str, Any] = {
    "name": MANAGE_CANDIDATE_COMMUNICATION,
    "description": (
        "Send a message to a candidate about their application. "
        "This could be a rejection, a status update, or a request "
        "for more information. The candidate will see this the next "
        "time they check their application status."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "application_id": {
                "type": "string",
                "description": "The application this message is about.",
            },
            "message": {
                "type": "string",
                "description": "The message to send to the candidate.",
            },
            "new_status": {
                "type": "string",
                "enum": ["rejected", "reviewed", "advanced"],
                "description": (
                    "Update the application status. Use 'rejected' "
                    "to close the loop, 'reviewed' to acknowledge "
                    "receipt, or 'advanced' to move them forward."
                ),
            },
        },
        "required": ["application_id", "message", "new_status"],
    },
}

_NUDGE_HIRING_MANAGER: dict[str, Any] = {
    "name": NUDGE_HIRING_MANAGER,
    "description": (
        "Send a follow-up message to a hiring manager who hasn't "
        "acted on forwarded candidates. Sometimes HMs go quiet. "
        "This is how you push them to make a decision."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "hiring_manager_id": {
                "type": "string",
                "description": "The hiring manager to nudge.",
            },
            "posting_id": {
                "type": "string",
                "description": "The posting you're nudging about.",
            },
            "message": {
                "type": "string",
                "description": (
                    "Your nudge message. Tone matters -- too pushy "
                    "and you damage the relationship, too soft and "
                    "nothing happens."
                ),
            },
        },
        "required": ["hiring_manager_id", "posting_id", "message"],
    },
}

_POST_OR_ADJUST_LISTING: dict[str, Any] = {
    "name": POST_OR_ADJUST_LISTING,
    "description": (
        "Create a new job posting or adjust an existing one. You "
        "might update requirements, salary range, or description "
        "based on what you're seeing in the candidate pool."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "posting_id": {
                "type": "string",
                "description": ("ID of existing posting to adjust, or omit to create a new one."),
            },
            "adjustments": {
                "type": "string",
                "description": "What to change and why.",
            },
        },
    },
}

_SCHEDULE_INTERVIEW: dict[str, Any] = {
    "name": SCHEDULE_INTERVIEW,
    "description": (
        "Schedule an interview between a candidate and a hiring "
        "manager or yourself. Requires the candidate to have been "
        "advanced past screening."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "application_id": {
                "type": "string",
                "description": "The application to schedule for.",
            },
            "interviewer_type": {
                "type": "string",
                "enum": ["recruiter", "hiring_manager"],
                "description": "Who will conduct the interview.",
            },
        },
        "required": ["application_id", "interviewer_type"],
    },
}


_REVIEW_FORWARDED_CANDIDATES: dict[str, Any] = {
    "name": REVIEW_FORWARDED_CANDIDATES,
    "description": (
        "Look at the candidates the recruiter sent you and decide "
        "who to interview. You can see the recruiter's framing, but "
        "form your own opinion. You can filter by a specific posting "
        "or see all forwarded candidates."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "posting_id": {
                "type": "string",
                "description": (
                    "Filter to candidates for a specific posting. "
                    "Leave empty to see all forwarded candidates."
                ),
            },
        },
    },
}

_ADVANCE_CANDIDATE: dict[str, Any] = {
    "name": ADVANCE_CANDIDATE,
    "description": (
        "Move a forwarded candidate to the interview stage. This "
        "signals that you want to talk to them. The interview will "
        "be scheduled automatically."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "application_id": {
                "type": "string",
                "description": "The application to advance.",
            },
        },
        "required": ["application_id"],
    },
}

_CONDUCT_INTERVIEW: dict[str, Any] = {
    "name": CONDUCT_INTERVIEW,
    "description": (
        "Have a technical or behavioral conversation with a "
        "candidate. Evaluate on your own criteria."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "interview_id": {
                "type": "string",
                "description": "The scheduled interview to conduct.",
            },
        },
        "required": ["interview_id"],
    },
}

_GIVE_FEEDBACK_TO_RECRUITER: dict[str, Any] = {
    "name": GIVE_FEEDBACK_TO_RECRUITER,
    "description": (
        "Tell the recruiter what you thought about a candidate or "
        "what you want to see differently in the pipeline. You "
        "decide how specific or vague to be."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "recruiter_id": {
                "type": "string",
                "description": "The recruiter to send feedback to.",
            },
            "posting_id": {
                "type": "string",
                "description": "The posting this feedback relates to.",
            },
            "feedback": {
                "type": "string",
                "description": (
                    "Your feedback. Could be about a specific "
                    "candidate, the overall pipeline quality, or "
                    "what you'd like to see more or less of."
                ),
            },
        },
        "required": ["recruiter_id", "posting_id", "feedback"],
    },
}

_APPROVE_OFFER: dict[str, Any] = {
    "name": APPROVE_OFFER,
    "description": (
        "Decide compensation, level, and whether to extend an offer. "
        "Can push above budget if you argue for it."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "application_id": {
                "type": "string",
                "description": "The candidate to extend an offer to.",
            },
            "base_salary": {
                "type": "integer",
                "description": "Proposed base salary in dollars.",
            },
            "additional_details": {
                "type": "string",
                "description": (
                    "Any additional offer details: equity, bonus, "
                    "signing bonus, level, or other terms."
                ),
            },
        },
        "required": ["application_id", "base_salary"],
    },
}

_REJECT_CANDIDATE: dict[str, Any] = {
    "name": REJECT_CANDIDATE,
    "description": (
        "Pass on a candidate with reasoning that goes back to the "
        "recruiter. Your reason helps the recruiter calibrate future "
        "screening."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "application_id": {
                "type": "string",
                "description": "The application to reject.",
            },
            "reason": {
                "type": "string",
                "description": (
                    "Why you're passing. This goes to the recruiter "
                    "and shapes what they send you next."
                ),
            },
        },
        "required": ["application_id", "reason"],
    },
}

_REQUEST_ROLE_CHANGE: dict[str, Any] = {
    "name": REQUEST_ROLE_CHANGE,
    "description": (
        "Tell the recruiter to adjust the posting. Change the level, "
        "split the role, modify requirements, or update the "
        "description based on what the market is telling you."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "posting_id": {
                "type": "string",
                "description": "The posting to change.",
            },
            "requested_changes": {
                "type": "string",
                "description": "What to change and why.",
            },
        },
        "required": ["posting_id", "requested_changes"],
    },
}


def job_seeker_tools() -> list[dict[str, Any]]:
    """Returns the full tool set for a jobseeker agent."""
    return [
        _BROWSE_JOB_BOARD,
        _RESEARCH_COMPANY,
        _WRITE_RESUME,
        _WRITE_COVER_LETTER,
        _SUBMIT_APPLICATION,
        _CHECK_APPLICATION_STATUS,
        _REVIEW_APPLICATION_HISTORY,
        _RESPOND_TO_RECRUITER,
        _DO_INTERVIEW,
        _EVALUATE_OFFER,
        _NEGOTIATE_OFFER,
        _ACCEPT_OFFER,
        _DECLINE_OFFER,
        _REFLECT,
    ]


def recruiter_tools() -> list[dict[str, Any]]:
    """Returns the full tool set for a recruiter agent."""
    return [
        _SCREEN_APPLICATIONS,
        _FORWARD_TO_HIRING_MANAGER,
        _MANAGE_CANDIDATE_COMMUNICATION,
        _NUDGE_HIRING_MANAGER,
        _POST_OR_ADJUST_LISTING,
        _SCHEDULE_INTERVIEW,
        _REFLECT,
    ]


def hiring_manager_tools() -> list[dict[str, Any]]:
    """Returns the full tool set for a hiring manager agent."""
    return [
        _REVIEW_FORWARDED_CANDIDATES,
        _ADVANCE_CANDIDATE,
        _CONDUCT_INTERVIEW,
        _GIVE_FEEDBACK_TO_RECRUITER,
        _APPROVE_OFFER,
        _REJECT_CANDIDATE,
        _REQUEST_ROLE_CHANGE,
        _REFLECT,
    ]
