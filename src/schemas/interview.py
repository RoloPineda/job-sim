"""Data structures for interview interactions between agents.

Keeps the interview contract in schemas so both the engine orchestrator
and agent assess_interview() methods can reference it without circular
imports.
"""

from dataclasses import dataclass, field


@dataclass
class InterviewData:
    """Context passed to an agent's assess_interview() after completion.

    Carries everything an agent needs to write its post-interview
    assessment. The agent's own profile and state are already on
    ``self``, so this only contains shared interview artifacts.

    Attributes:
        transcript: Ordered list of speaker turns. Each entry has
            ``speaker`` (agent name) and ``content`` (what they said).
        role_context: Description of the role under discussion and
            any relevant context both parties were given.
        other_party_name: Name of the other participant.
    """

    transcript: list[dict[str, str]] = field(default_factory=list)
    role_context: str = ""
    other_party_name: str = ""


def format_transcript(transcript: list[dict[str, str]]) -> str:
    """Format an interview transcript for inclusion in a prompt.

    Args:
        transcript: Ordered speaker turns with ``speaker`` and
            ``content`` keys.

    Returns:
        Human-readable transcript with speakers labeled and turns
        separated by blank lines.
    """
    lines = []
    for entry in transcript:
        lines.append(f"{entry['speaker']}: {entry['content']}")
    return "\n\n".join(lines)