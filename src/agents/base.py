"""Base agent class with API call infrastructure and tool-use harness.

Provides the shared mechanics that all agent types need: calling the
Anthropic API with retry/backoff, running the tool-use loop with a
soft cap, and tracking usage for monitoring. Subclasses implement four
abstract methods to define agent-type-specific behavior.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from anthropic import (
    APIConnectionError,
    APIError,  # noqa: F401 — re-exported for callers, referenced in docstrings
    APITimeoutError,
    AsyncAnthropic,
    RateLimitError,
)
from anthropic.types import Message, ToolUseBlock

from engine.prompt_builder import PromptBuilder
from schemas.config import RunConfig
from schemas.interview import InterviewData
from schemas.profiles import AgentProfile

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_DELAY_SECONDS = 1.0
_RETRYABLE_ERRORS = (RateLimitError, APITimeoutError, APIConnectionError)
_MAX_TOKENS = 4096

_SOFT_CAP_NUDGE = (
    "\n\nYou're running low on time today. You can take one more "
    "action or wrap up for the day."
)

# Approximate values for development monitoring. Not used for
# billing, just to estimate spend during runs so you can
# catch runaway costs early. Update if pricing changes
# Per-million token pricing (input, output) e.g., sonnet (3.0, 15.0)
# Sonnet costs $3 per 1 million input tokens and $15 for 1m output tokens
# Models used: Sonnet 4.6, Opus 4.6, Haiku 4.5 as of 3/3/2026
_PRICING: dict[str, tuple[float, float]] = {
    "sonnet": (3.0, 15.0),
    "haiku": (1, 5.0),
    "opus": (5.0, 25.0),
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate API cost in dollars from token counts."""
    for tier, (inp, out) in _PRICING.items():
        if tier in model:
            return (input_tokens * inp + output_tokens * out) / 1_000_000
    return 0.0


def _model_short(model: str) -> str:
    """Extract tier name from a model version string."""
    for tier in _PRICING:
        if tier in model:
            return tier
    return model


@dataclass
class TurnResult:
    """Summary of a single agent turn."""

    tool_calls_made: int = 0
    api_calls_made: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    soft_cap_hit: bool = False
    skipped: bool = False
    skip_reason: str | None = None


class BaseAgent(ABC):
    """Abstract base for all simulation agents.

    Provides the tool-use harness and API call infrastructure.
    Subclasses implement four abstract methods to define behavior
    specific to their role (jobseeker, recruiter, hiring manager).

    Args:
        profile: The agent's immutable identity and disposition.
        config: Simulation-wide parameters.
        client: Anthropic async client. Injected for testing;
            a default client is created if omitted.
    """

    def __init__(
        self,
        profile: AgentProfile,
        config: RunConfig,
        *,
        client: AsyncAnthropic | None = None,
    ) -> None:
        self.profile = profile
        self._config = config
        self._client = client or AsyncAnthropic()
        self._prompt_builder = PromptBuilder(config)

    @abstractmethod
    def get_tools(self) -> list[dict[str, Any]]:
        """Return tool definitions formatted for the Anthropic API."""

    @abstractmethod
    def build_context(self) -> str:
        """Assemble agent-specific context for the user message."""

    @abstractmethod
    async def handle_tool_call(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool call and return the result string."""

    async def screen_candidate(self, interaction: Any) -> str:
        """Produce a pre-interview screening assessment.

        Evaluates a candidate's application materials before deciding
        whether to advance them to an interview. Override in agent
        types that perform candidate screening (recruiter, hiring
        manager).

        Args:
            interaction: Screening data, typically a dict containing
                an ``application_id`` key.

        Returns:
            Screening assessment string.

        Raises:
            NotImplementedError: If the agent type does not support
                candidate screening.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support candidate screening"
        )

    async def assess_interview(self, data: "InterviewData") -> str:
        """Produce a post-interview assessment.

        Called by the interview orchestrator after the conversation
        loop completes. Override in agent types that participate in
        interviews.

        Args:
            data: Interview transcript, role context, and the other
                party's name.

        Returns:
            Written assessment string. Interviewer assessments must
            end with a ``DECISION: ADVANCE/REJECT/UNDECIDED`` line.

        Raises:
            NotImplementedError: If the agent type does not support
                interview assessment.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support interview assessment"
        )

    async def run_turn(
        self,
        round_number: int,
        notifications: list[str] | None = None,
    ) -> TurnResult:
        """Execute this agent's turn within a round.

        Builds the prompt, calls the API in a loop, executes tool
        calls, and manages the soft cap. Returns a summary of what
        happened during the turn.

        Args:
            round_number: Current simulation round.
            notifications: Pending updates for the agent.

        Returns:
            Summary with token usage, tool call counts, and
            whether the turn was skipped or capped.
        """
        payload = self._prompt_builder.build_action_payload(
            self.profile,
            self.build_context(),
            round_number,
            self.get_tools(),
            notifications,
        )

        system = payload["system"]
        messages: list[dict[str, Any]] = list(payload["messages"])
        tools = payload.get("tools")
        model = self._config.sonnet_model_version

        result = TurnResult()
        nudged = False

        while True:
            response = await self._try_api_call(system, messages, tools, model, result)
            if response is None:
                break

            self._track_usage(response, model, result)

            tool_use_blocks = self._extract_tool_blocks(response)
            if tool_use_blocks is None:
                break

            # Serialize the full response (text + tool_use blocks) back
            # into the conversation so the model sees its own prior
            # output on the next loop iteration.
            messages.append(
                {
                    "role": "assistant",
                    "content": [
                        b.model_dump(exclude_none=True) for b in response.content
                    ],
                }
            )

            tool_results = await self._execute_tool_calls(tool_use_blocks, result)

            if nudged:
                # Agent got one final exchange after the soft cap nudge.
                # End the turn regardless of whether it made more tool
                # calls. What it chose to do with its last action is
                # behavioral data.
                break

            nudged = self._apply_soft_cap(tool_results, result)
            messages.append({"role": "user", "content": tool_results})

        self._print_turn_summary(result)
        return result

    async def _try_api_call(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str,
        result: TurnResult,
    ) -> Message | None:
        """Attempt an API call, returning None if it fails after retries.

        Args:
            system: System prompt string.
            messages: Conversation history.
            tools: Tool definitions.
            model: Model version string.
            result: Turn result to update on failure.

        Returns:
            The API response, or None if the call failed and the
            turn should be skipped.
        """
        try:
            return await self.call_api(system, messages, tools, model)
        except Exception as exc:
            result.skipped = True
            result.skip_reason = f"api_failure: {type(exc).__name__}"
            logger.warning(
                "[%s] turn skipped after API failure: %s",
                self.profile.id,
                exc,
            )
            return None

    def _track_usage(self, response: Message, model: str, result: TurnResult) -> None:
        """Accumulate token counts and cost from an API response.

        Args:
            response: The API response message.
            model: Model version string used for cost estimation.
            result: Turn result to update.
        """
        result.api_calls_made += 1
        result.total_input_tokens += response.usage.input_tokens
        result.total_output_tokens += response.usage.output_tokens
        result.total_cost += _estimate_cost(
            model,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )

    def _extract_tool_blocks(self, response: Message) -> list[ToolUseBlock] | None:
        """Extract tool-use blocks from an API response.

        Returns None if the response is empty or contains no tool
        calls, signaling the turn should end.

        Args:
            response: The API response message.

        Returns:
            List of tool-use blocks, or None if the turn should end.
        """
        if not response.content:
            logger.warning(
                "[%s] empty response from API, ending turn",
                self.profile.id,
            )
            return None

        tool_use_blocks = [b for b in response.content if isinstance(b, ToolUseBlock)]

        if not tool_use_blocks:
            return None

        return tool_use_blocks

    async def _execute_tool_calls(
        self,
        blocks: list[ToolUseBlock],
        result: TurnResult,
    ) -> list[dict[str, Any]]:
        """Execute tool calls and collect results.

        Each tool call is run through the subclass handle_tool_call
        method. Failures are returned as error results to the model
        rather than crashing the turn.

        Args:
            blocks: Tool-use blocks from the API response.
            result: Turn result to update with call counts.

        Returns:
            Tool result dicts ready to append to the conversation.
        """
        tool_results: list[dict[str, Any]] = []
        for block in blocks:
            result.tool_calls_made += 1
            try:
                tool_output = await self.handle_tool_call(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(tool_output),
                    }
                )
            except Exception as exc:
                logger.warning(
                    "[%s] tool %s failed: %s",
                    self.profile.id,
                    block.name,
                    exc,
                )
                # Return the error to the model rather than crashing
                # the turn. is_error tells the API this was a failed
                # tool call, letting the model retry or move on.
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Error executing {block.name}: {exc}",
                        "is_error": True,
                    }
                )
        return tool_results

    def _apply_soft_cap(
        self,
        tool_results: list[dict[str, Any]],
        result: TurnResult,
    ) -> bool:
        """Check the soft cap and inject a nudge if reached.

        Nudge rides on the last tool result rather than as a separate
        message because the API requires strict user/assistant
        alternation.

        Args:
            tool_results: Tool results for the current exchange.
                The last entry's content may be modified in place.
            result: Turn result to update.

        Returns:
            True if the soft cap was hit and the nudge was injected.
        """
        if result.tool_calls_made >= self._config.tool_call_soft_cap:
            result.soft_cap_hit = True
            if tool_results:
                tool_results[-1]["content"] += _SOFT_CAP_NUDGE
            logger.info(
                "[%s] soft cap hit at %d tool calls",
                self.profile.id,
                result.tool_calls_made,
            )
            return True
        return False

    async def call_api(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> Message:
        """Call the Anthropic Messages API with retry and backoff.

        Retries on rate limits, timeouts, and connection errors
        with exponential backoff. Prints a summary line per call
        for real-time monitoring during development.

        Args:
            system: System prompt string.
            messages: Conversation history.
            tools: Tool definitions, or None for tool-free calls.
            model: Model version string. Defaults to the sonnet
                version from config.

        Returns:
            The API response message.

        Raises:
            APIError: On non-retryable errors, or after all retries
                are exhausted for retryable errors.
        """
        model = model or self._config.sonnet_model_version

        kwargs: dict[str, Any] = {
            "model": model,
            "system": system,
            "messages": messages,
            "max_tokens": _MAX_TOKENS,
            "temperature": self._config.temperature,
            "top_p": self._config.top_p,
        }
        if tools:
            kwargs["tools"] = tools

        for attempt in range(_MAX_RETRIES + 1):
            t0 = time.monotonic()
            try:
                response = await self._client.messages.create(**kwargs)
                latency_ms = (time.monotonic() - t0) * 1000
                cost = _estimate_cost(
                    model,
                    response.usage.input_tokens,
                    response.usage.output_tokens,
                )
                print(
                    f"[{self.profile.id}] {_model_short(model)} | "
                    f"{response.usage.input_tokens:,}→"
                    f"{response.usage.output_tokens:,} tok | "
                    f"${cost:.4f} | "
                    f"{latency_ms:.0f}ms | "
                    f"retries={attempt}"
                )
                return response

            except _RETRYABLE_ERRORS as exc:
                latency_ms = (time.monotonic() - t0) * 1000
                if attempt == _MAX_RETRIES:
                    print(
                        f"[{self.profile.id}] {_model_short(model)} | "
                        f"FAILED after {_MAX_RETRIES} retries | "
                        f"{type(exc).__name__} | {latency_ms:.0f}ms"
                    )
                    raise
                delay = _BASE_DELAY_SECONDS * (2**attempt)
                print(
                    f"[{self.profile.id}] retry {attempt + 1}/"
                    f"{_MAX_RETRIES}: {type(exc).__name__} after "
                    f"{latency_ms:.0f}ms, waiting {delay:.1f}s"
                )
                await asyncio.sleep(delay)

        raise AssertionError("retry loop exited unexpectedly")

    def _print_turn_summary(self, result: TurnResult) -> None:
        """Print a one-line turn summary for development monitoring."""
        if result.skipped:
            print(
                f"[{self.profile.id}] turn skipped: "
                f"{result.skip_reason} | "
                f"{result.api_calls_made} api calls | "
                f"{result.total_input_tokens:,}→"
                f"{result.total_output_tokens:,} tok | "
                f"${result.total_cost:.4f}"
            )
        else:
            print(
                f"[{self.profile.id}] turn complete | "
                f"{result.tool_calls_made} tool calls | "
                f"{result.api_calls_made} api calls | "
                f"{result.total_input_tokens:,}→"
                f"{result.total_output_tokens:,} tok | "
                f"${result.total_cost:.4f} | "
                f"soft_cap={'yes' if result.soft_cap_hit else 'no'}"
            )
