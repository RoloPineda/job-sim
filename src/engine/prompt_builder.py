"""Prompt assembly for the Anthropic Messages API.

Combines agent profiles, accumulated context, and tool definitions into
API-ready message structures. This module handles formatting only, all
content generation (context building, history compression) happens
elsewhere.
"""

from typing import Any, Literal, NotRequired, TypedDict, cast

from anthropic.types import MessageParam

from schemas.config import RunConfig
from schemas.profiles import AgentProfile

_SEEKER_INSTRUCTIONS = (
    "You are looking for work. Make decisions based on your skills, "
    "preferences, and financial situation. When evaluating opportunities, "
    "consider what matters to you: compensation, role fit, company culture, "
    "growth potential, and weigh those against your circumstances.\n\n"
    "When communicating with recruiters and interviewers, be professional "
    "but authentic. Your communication style should reflect your personality. "
    "You can choose how much effort to put into each application and how "
    "selective to be."
)

_RECRUITER_INSTRUCTIONS = (
    "You manage hiring pipelines for your assigned roles. Your job is to "
    "find strong candidates, screen them, and work with your hiring managers "
    "to fill open positions. Balance quality with speed. Open roles cost "
    "money, but bad hires are worse.\n\n"
    "When screening candidates, consider the requirements for each role and "
    "what you know about what each hiring manager values. How you communicate "
    "with candidates and how quickly you respond is up to you."
)

_HM_INSTRUCTIONS = (
    "You are responsible for building and maintaining your team. You set the "
    "bar for who gets hired, conduct interviews, and make final decisions on "
    "offers. Work with your recruiter to communicate what you need.\n\n"
    "When evaluating candidates, apply your own judgment and standards. "
    "Consider technical ability, team fit, and what your team actually needs "
    "right now."
)

_INTERVIEWER_TYPES = {"recruiter", "hiring_manager"}

_INTERVIEWER_INSTRUCTIONS = (
    "Ask questions and make statements as you naturally would. "
    "Do not explain what you are testing for or what a question "
    "is designed to reveal."
)

_BEHAVIORAL_INSTRUCTIONS: dict[str, str] = {
    "job_seeker": _SEEKER_INSTRUCTIONS,
    "recruiter": _RECRUITER_INSTRUCTIONS,
    "hiring_manager": _HM_INSTRUCTIONS,
}

_ROLE_LABELS: dict[str, str] = {
    "job_seeker": "a professional",
    "recruiter": "a recruiter",
    "hiring_manager": "a hiring manager",
}

_CLOSING_PROMPTS: dict[str, str] = {
    "job_seeker": "What would you like to do?",
    "recruiter": "How would you like to proceed?",
    "hiring_manager": "How would you like to proceed?",
}

_REQUIRED_TOOL_KEYS = {"name", "description", "input_schema"}


class MessagePayload(TypedDict):
    """Complete payload for a single Anthropic Messages API call."""

    system: str
    messages: list[MessageParam]
    tools: NotRequired[list[dict[str, Any]]]


class PromptBuilder:
    """Assembles API-ready prompts from agent profiles and state.

    Handles the mechanics of combining system messages, context, tool
    definitions, and conversation history into the format the Anthropic
    API expects. Never references the simulation, agents are framed as
    real people in their situation.
    """

    def __init__(self, config: RunConfig) -> None:
        self._interview_turn_ceiling = config.interview_turn_ceiling

    def build_system_message(self, profile: AgentProfile) -> str:
        """Create the system prompt from an agent profile.

        The system prompt anchors the agent's persona across all rounds.
        It includes identity, disposition, backstory, and behavioral
        instructions appropriate to the agent type. Disposition comes
        before backstory so personality traits prime how the narrative
        is interpreted.

        Args:
            profile: The agent's immutable profile.

        Returns:
            The assembled system prompt string.
        """
        role_label = _ROLE_LABELS[profile.agent_type]
        instructions = _BEHAVIORAL_INSTRUCTIONS[profile.agent_type]

        return (
            f"You are {profile.name}, {role_label} based in "
            f"{profile.location}.\n\n"
            f"{profile.disposition}\n\n"
            f"{profile.backstory}\n\n"
            f"{instructions}"
            "Respond with only your spoken words. Do not include "
            "actions, stage directions, gestures, or descriptions "
            "of body language. Do not compliment or validate the "
            "other person's questions or statements before answering."
            "Do not open your response by agreeing with, complimenting, "
            "or acknowledging the other person's question or statement. "
            "Answer directly."
        )

    def build_user_message(
        self,
        context: str,
        round_number: int,
        agent_type: str,
        notifications: list[str] | None = None,
    ) -> str:
        """Create the user message with round context.

        Combines agent-specific context (from agent.build_context()) with
        round metadata and any pending notifications.

        Args:
            context: Agent-specific context string from build_context().
            round_number: Current simulation round.
            agent_type: The agent's type, used to select an appropriate
                closing prompt.
            notifications: Pending updates like application status
                changes or interview scheduling.

        Returns:
            The assembled user message string.
        """
        parts = [f"Current round: {round_number}\n", context]

        if notifications:
            items = "\n".join(f"- {n}" for n in notifications)
            parts.append(f"Recent updates:\n{items}")

        parts.append(_CLOSING_PROMPTS[agent_type])
        return "\n\n".join(parts)

    def format_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Format tool definitions for the Anthropic Messages API.

        Validates that each tool definition contains the required fields
        and returns them in the expected schema.

        Args:
            tools: Raw tool definitions from agent.get_tools().

        Returns:
            Validated tool definitions ready for the API.

        Raises:
            ValueError: If a tool definition is missing required fields.
        """
        formatted: list[dict[str, Any]] = []
        for tool in tools:
            missing = _REQUIRED_TOOL_KEYS - tool.keys()
            if missing:
                raise ValueError(
                    f"Tool '{tool.get('name', '<unnamed>')}' is missing "
                    f"required fields: {', '.join(sorted(missing))}"
                )
            formatted.append(
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "input_schema": tool["input_schema"],
                }
            )
        return formatted

    def build_action_payload(
        self,
        profile: AgentProfile,
        context: str,
        round_number: int,
        tools: list[dict[str, Any]],
        notifications: list[str] | None = None,
    ) -> MessagePayload:
        """Assemble a complete payload for an agent's regular turn.

        Combines the system prompt, user message, and tool definitions
        into a single API-ready structure.

        Args:
            profile: The agent's immutable profile.
            context: Agent-specific context string from build_context().
            round_number: Current simulation round.
            tools: Raw tool definitions from agent.get_tools().
            notifications: Pending updates for the agent.

        Returns:
            Complete message payload for the API call.
        """
        system = self.build_system_message(profile)
        user = self.build_user_message(context, round_number, profile.agent_type, notifications)
        formatted_tools = self.format_tools(tools)

        payload = MessagePayload(
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        if formatted_tools:
            payload["tools"] = formatted_tools
        return payload

    def build_interview_turn(
        self,
        speaker_profile: AgentProfile,
        role_context: str,
        transcript: list[dict[str, str]],
        turn_number: int,
    ) -> MessagePayload:
        """Build the prompt for a single interview turn.

        Assembles the speaking agent's system prompt, interview context,
        and conversation transcript into a complete API payload. Adds
        wrap-up cues when the conversation approaches the turn ceiling.

        No tools are provided because interviews are freeform
        conversation, not tool-use turns.

        Args:
            speaker_profile: Profile of the agent whose turn it is.
            role_context: Description of the role being discussed and
                who the other party is.
            transcript: Conversation so far as dicts with ``speaker``
                and ``content`` keys.
            turn_number: Current turn in the interview (1-indexed).

        Returns:
            Complete message payload for the API call.
        """
        system = self.build_system_message(speaker_profile)
        if speaker_profile.agent_type in _INTERVIEWER_TYPES:
            system += "\n\n" + _INTERVIEWER_INSTRUCTIONS
        messages = self._build_interview_messages(speaker_profile.name, role_context, transcript)
        # Inject one turn before the hard stop so the agent can close
        # naturally rather than getting cut off mid-thought.
        if turn_number >= self._interview_turn_ceiling - 1:
            messages[-1]["content"] += (
                "\n\nThis conversation is wrapping up. Consider "
                "bringing your remaining points to a close."
            )

        return MessagePayload(system=system, messages=cast(list[MessageParam], messages))

    def _build_interview_messages(
        self,
        speaker_name: str,
        role_context: str,
        transcript: list[dict[str, str]],
    ) -> list[MessageParam]:
        """Convert a transcript into API-ready messages.

        Maps speaker names to API roles (the current speaker becomes
        "assistant", everyone else becomes "user"), then merges and
        fixes alternation issues.

        Args:
            speaker_name: Name of the agent whose turn it is.
            role_context: Opening context provided as the first user
                message.
            transcript: Conversation so far as dicts with ``speaker``
                and ``content`` keys.

        Returns:
            Messages list ready for the API, guaranteed to end with a
            user message.
        """
        raw: list[MessageParam] = [{"role": "user", "content": role_context}]
        for entry in transcript:
            role: Literal["user", "assistant"] = (
                "assistant" if entry["speaker"] == speaker_name else "user"
            )
            raw.append({"role": role, "content": entry["content"]})

        messages = self._merge_consecutive_roles(raw)

        # The transcript can end on the current speaker's own prior
        # turn if the other party hasn't responded yet. The API
        # requires the final message to be a user message.
        if messages[-1]["role"] == "assistant":
            messages.append({"role": "user", "content": "Please continue."})

        return messages

    @staticmethod
    def _extract_text(content: str | list[Any]) -> str:
        """Extracts plain text from a MessageParam content field.

        Handles both the simple string form and the list-of-blocks form
        that the Anthropic API supports.

        Args:
            content: Either a plain string or a list of content blocks,
                where text blocks have a "text" key.

        Returns:
            The concatenated text content.
        """
        if isinstance(content, str):
            return content
        return "\n".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )

    @staticmethod
    def _merge_consecutive_roles(
        messages: list[MessageParam],
    ) -> list[MessageParam]:
        """Merge consecutive messages with the same role.

        The transcript stores one entry per speaker turn, but a speaker
        can have multiple entries in a row (e.g., interviewer asks a
        question then adds a follow-up before the candidate responds).
        The Anthropic API requires strict user/assistant alternation, so
        consecutive same-role entries are joined with a blank line.

        Args:
            messages: Raw message list that may have consecutive
                same-role entries.

        Returns:
            New list with consecutive same-role messages merged.
        """
        merged: list[MessageParam] = [messages[0]]
        for msg in messages[1:]:
            if msg["role"] == merged[-1]["role"]:
                existing = PromptBuilder._extract_text(merged[-1]["content"])
                new = PromptBuilder._extract_text(msg["content"])
                merged[-1] = {
                    "role": msg["role"],
                    "content": existing + "\n\n" + new,
                }
            else:
                merged.append(msg)
        return merged

    def build_reflection_prompt(
        self,
        profile: AgentProfile,
        context_summary: str,
    ) -> MessagePayload:
        """Build the prompt for an agent self-reflection.

        Produces a payload that asks the agent to assess its current
        situation. The response is stored as a ReflectionEntry and fed
        back into future context.

        Args:
            profile: The agent's immutable profile.
            context_summary: Summary of the agent's current state and
                recent history.

        Returns:
            Complete message payload for the reflection API call.
        """
        system = self.build_system_message(profile)

        user_content = (
            f"{context_summary}\n\n"
            "Take a step back and reflect on how things are going. "
            "What's working? What isn't? Is there anything you'd do "
            "differently going forward?"
        )

        return MessagePayload(
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
