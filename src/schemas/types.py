"""Shared type definitions for the Candor simulation."""

from typing import Literal

AgentType = Literal["job_seeker", "recruiter", "hiring_manager"]
ApplicationStatus = Literal["pending", "reviewed", "rejected", "advanced", "ghosted"]
Seniority = Literal["junior", "mid", "senior", "lead", "staff"]
SelfAwareness = Literal["accurate", "overconfident", "underconfident"]
CommunicationAbility = Literal["strong", "average", "weak"]
LocationFlexibility = Literal["rigid", "moderate", "flexible"]
RemotePreference = Literal["remote_only", "hybrid", "onsite", "no_preference"]
ExperienceLevel = Literal["junior", "mid", "senior"]
TeamSituation = Literal["understaffed", "stable", "growing", "rebuilding"]
ManagementStyle = Literal["detailed_feedback", "vague", "responsive", "slow", "micromanager"]
FeedbackClarity = Literal["clear", "vague", "contradictory"]
PostingStatus = Literal["open", "closed", "filled", "expired"]
MessageType = Literal["candidate_forward", "feedback", "nudge", "role_change_request"]
ResumeTrigger = Literal["initial", "general_rewrite", "tailored"]