"""History compression for agent context management.

Uses a lightweight model (Haiku) to compress older events into a
running summary. Events within the recent history window stay raw.
Everything older gets folded into compressed_history on the agent's
state.
"""

import logging
from typing import Any

from anthropic import AsyncAnthropic
from anthropic.types import MessageParam

from schemas.config import RunConfig
from schemas.states import AgentState

logger = logging.getLogger(__name__)

# TODO: Monitor whether this creates truncated responses or not
_MAX_TOKENS = 1024

_SYSTEM_PROMPT = (
    "You are a concise summarizer. Your job is to compress a list of "
    "events from an agent's recent history into a short narrative "
    "summary. Preserve key details: what happened, what the outcomes "
    "were, and any notable shifts in strategy or situation. Drop "
    "redundant or trivial events. Integrate new events with any "
    "existing summary rather than repeating it."
)


def should_compress(state: AgentState, config: RunConfig) -> bool:
    """Determines whether compression is due for this agent.

    The compression frequency is set via config.compression_frequency.

    Args:
        state: The agent's current mutable state.
        config: Simulation configuration with compression parameters.

    Returns:
        True if the current round triggers compression.
    """
    return (
        state.round_number > 1
        and state.round_number % config.compression_frequency == 0
    )


def _partition_events(
    state: AgentState, config: RunConfig
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Splits events into those to compress and those to keep raw.

    Events within the recent_history_window stay raw. Everything
    older is eligible for compression.

    Args:
        state: The agent's current state.
        config: Simulation configuration with window parameters.

    Returns:
        Tuple of (events_to_compress, events_to_keep).
    """
    cutoff = state.round_number - config.recent_history_window
    to_compress = []
    to_keep = []

    for event in state.recent_events:
        event_round = event.get("round", event.get("round_number", 0))
        if event_round < cutoff:
            to_compress.append(event)
        else:
            to_keep.append(event)

    return to_compress, to_keep


def _format_events_for_compression(
    events: list[dict[str, Any]],
) -> str:
    """Formats events into a readable string for the compression prompt.

    Args:
        events: Events to format.

    Returns:
        Formatted event list as a string.
    """
    lines = []
    for event in events:
        description = event.get("description", str(event))
        event_round = event.get("round", event.get("round_number", "?"))
        lines.append(f"- Round {event_round}: {description}")
    return "\n".join(lines)


async def compress_history(
    state: AgentState,
    config: RunConfig,
    client: AsyncAnthropic,
    agent_id: str,
) -> None:
    """Compresses older events into the agent's compressed_history.

    Partitions events by the recent_history_window, sends the older
    batch to Haiku for summarization, and updates the state in place.
    Skips the API call if there are no events to compress.

    Args:
        state: The agent's mutable state, modified in place.
        config: Simulation configuration.
        client: Anthropic async client for the Haiku call.
        agent_id: Agent identifier for logging.
    """
    to_compress, to_keep = _partition_events(state, config)

    if not to_compress:
        return

    formatted = _format_events_for_compression(to_compress)

    user_content = ""
    if state.compressed_history:
        user_content += f"Existing summary:\n{state.compressed_history}\n\n"
    user_content += (
        f"New events to integrate:\n{formatted}\n\n"
        "Produce an updated summary that integrates the new events "
        "with the existing summary. Be concise."
    )

    messages: list[MessageParam] = [{"role": "user", "content": user_content}]

    response = await client.messages.create(
        model=config.haiku_model_version,
        system=_SYSTEM_PROMPT,
        messages=messages,
        max_tokens=_MAX_TOKENS,
    )

    compressed = ""
    for block in response.content:
        if hasattr(block, "text"):
            compressed += block.text

    state.compressed_history = compressed.strip()
    state.recent_events = to_keep

    logger.info(
        "[%s] compressed %d events into %d chars, %d events kept raw",
        agent_id,
        len(to_compress),
        len(state.compressed_history),
        len(to_keep),
    )
