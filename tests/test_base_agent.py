"""Tests for the base agent tool-use harness and API call infrastructure."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anthropic import RateLimitError
from anthropic.types import Message, TextBlock, ToolUseBlock, Usage

from agents.base import (
    BaseAgent,
    _estimate_cost,
    _model_short,
)
from tests.helpers import make_config, make_sample_tools, make_seeker_profile


def _make_usage(input_tokens: int = 100, output_tokens: int = 50) -> Usage:
    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )


def _make_text_response(text: str = "I'll think about it.") -> Message:
    return Message(
        id="msg_test",
        content=[TextBlock(type="text", text=text)],
        model="claude-sonnet-4-20250514",
        role="assistant",
        stop_reason="end_turn",
        type="message",
        usage=_make_usage(),
    )


def _make_tool_response(
    tool_name: str = "browse_job_board",
    tool_input: dict | None = None,
    tool_id: str = "toolu_test",
    text: str | None = None,
) -> Message:
    content = []
    if text:
        content.append(TextBlock(type="text", text=text))
    content.append(
        ToolUseBlock(
            type="tool_use",
            id=tool_id,
            name=tool_name,
            input=tool_input or {},
        )
    )
    return Message(
        id="msg_test",
        content=content,
        model="claude-sonnet-4-20250514",
        role="assistant",
        stop_reason="tool_use",
        type="message",
        usage=_make_usage(),
    )


def _make_multi_tool_response(
    tools: list[tuple[str, dict, str]],
) -> Message:
    """Build a response with multiple tool use blocks.

    Args:
        tools: List of (name, input, id) tuples.
    """
    content = [
        ToolUseBlock(type="tool_use", id=tid, name=name, input=inp) for name, inp, tid in tools
    ]
    return Message(
        id="msg_test",
        content=content,
        model="claude-sonnet-4-20250514",
        role="assistant",
        stop_reason="tool_use",
        type="message",
        usage=_make_usage(),
    )


class StubAgent(BaseAgent):
    """Concrete subclass for testing the base harness."""

    def __init__(self, tools=None, context="test context", **kwargs):
        super().__init__(**kwargs)
        self._tools = tools or make_sample_tools()
        self._context = context
        self.tool_calls_received: list[tuple[str, dict]] = []

    def get_tools(self) -> list[dict[str, Any]]:
        return self._tools

    def build_context(self) -> str:
        return self._context

    async def handle_tool_call(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        self.tool_calls_received.append((tool_name, tool_input))
        return f"Result for {tool_name}"

    async def evaluate(self, interaction: Any) -> str:
        return "evaluation"


@pytest.fixture()
def config():
    return make_config()


@pytest.fixture()
def mock_client():
    client = AsyncMock()
    client.messages = AsyncMock()
    client.messages.create = AsyncMock()
    return client


@pytest.fixture()
def agent(config, mock_client):
    return StubAgent(
        profile=make_seeker_profile(),
        config=config,
        client=mock_client,
    )


class TestEstimateCost:
    def test_sonnet_pricing(self):
        cost = _estimate_cost("claude-sonnet-4-20250514", 1_000_000, 1_000_000)
        assert cost == pytest.approx(18.0)

    def test_haiku_pricing(self):
        cost = _estimate_cost("claude-haiku-4-20250414", 1_000_000, 1_000_000)
        assert cost == pytest.approx(6.0)

    def test_unknown_model_returns_zero(self):
        assert _estimate_cost("unknown-model", 1000, 1000) == 0.0

    def test_zero_tokens(self):
        assert _estimate_cost("claude-sonnet-4-20250514", 0, 0) == 0.0


class TestModelShort:
    def test_sonnet(self):
        assert _model_short("claude-sonnet-4-20250514") == "sonnet"

    def test_haiku(self):
        assert _model_short("claude-haiku-4-20250414") == "haiku"

    def test_unknown(self):
        assert _model_short("gpt-4") == "gpt-4"


class TestCallApi:
    @pytest.mark.asyncio
    async def test_successful_call(self, agent, mock_client):
        mock_client.messages.create.return_value = _make_text_response()
        response = await agent.call_api("system prompt", [{"role": "user", "content": "hello"}])
        assert response.content[0].text == "I'll think about it."
        mock_client.messages.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_passes_temperature_and_top_p(self, agent, mock_client):
        mock_client.messages.create.return_value = _make_text_response()
        await agent.call_api("system", [{"role": "user", "content": "hi"}])
        kwargs = mock_client.messages.create.call_args.kwargs
        assert kwargs["temperature"] == 0.7
        assert kwargs["top_p"] == 1.0

    @pytest.mark.asyncio
    async def test_passes_tools_when_provided(self, agent, mock_client):
        mock_client.messages.create.return_value = _make_text_response()
        tools = make_sample_tools()
        await agent.call_api(
            "system",
            [{"role": "user", "content": "hi"}],
            tools=tools,
        )
        kwargs = mock_client.messages.create.call_args.kwargs
        assert kwargs["tools"] == tools

    @pytest.mark.asyncio
    async def test_omits_tools_when_none(self, agent, mock_client):
        mock_client.messages.create.return_value = _make_text_response()
        await agent.call_api("system", [{"role": "user", "content": "hi"}])
        kwargs = mock_client.messages.create.call_args.kwargs
        assert "tools" not in kwargs

    @pytest.mark.asyncio
    async def test_retries_on_rate_limit(self, agent, mock_client):
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}
        rate_error = RateLimitError(
            message="rate limited",
            response=mock_response,
            body=None,
        )
        mock_client.messages.create.side_effect = [
            rate_error,
            _make_text_response(),
        ]
        with patch("agents.base.asyncio.sleep", new_callable=AsyncMock):
            response = await agent.call_api("system", [{"role": "user", "content": "hi"}])
        assert response.content[0].text == "I'll think about it."
        assert mock_client.messages.create.await_count == 2

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self, agent, mock_client):
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}
        rate_error = RateLimitError(
            message="rate limited",
            response=mock_response,
            body=None,
        )
        mock_client.messages.create.side_effect = rate_error
        with (
            patch("agents.base.asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(RateLimitError),
        ):
            await agent.call_api("system", [{"role": "user", "content": "hi"}])
        # 1 initial + 3 retries = 4 total attempts
        assert mock_client.messages.create.await_count == 4


class TestRunTurn:
    @pytest.mark.asyncio
    async def test_text_only_response_ends_turn(self, agent, mock_client):
        mock_client.messages.create.return_value = _make_text_response()
        result = await agent.run_turn(1)
        assert result.tool_calls_made == 0
        assert result.api_calls_made == 1
        assert not result.soft_cap_hit
        assert not result.skipped

    @pytest.mark.asyncio
    async def test_single_tool_call_then_text(self, agent, mock_client):
        mock_client.messages.create.side_effect = [
            _make_tool_response("browse_job_board", {"filter_role": "engineer"}),
            _make_text_response("Found some good options."),
        ]
        result = await agent.run_turn(1)
        assert result.tool_calls_made == 1
        assert result.api_calls_made == 2
        assert agent.tool_calls_received == [("browse_job_board", {"filter_role": "engineer"})]

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_in_one_response(self, agent, mock_client):
        multi = _make_multi_tool_response(
            [
                ("browse_job_board", {}, "toolu_1"),
                ("submit_application", {"posting_id": "p1"}, "toolu_2"),
            ]
        )
        mock_client.messages.create.side_effect = [
            multi,
            _make_text_response(),
        ]
        result = await agent.run_turn(1)
        assert result.tool_calls_made == 2
        assert len(agent.tool_calls_received) == 2

    @pytest.mark.asyncio
    async def test_tool_call_failure_feeds_error_back(self, agent, mock_client):
        """Malformed tool calls return error to model, don't crash."""

        async def failing_handle(name, inp):
            raise ValueError("missing required field")

        agent.handle_tool_call = failing_handle

        mock_client.messages.create.side_effect = [
            _make_tool_response("bad_tool", {}),
            _make_text_response("I see the error."),
        ]
        result = await agent.run_turn(1)
        assert result.tool_calls_made == 1
        assert not result.skipped
        # Check that error was fed back in messages
        user_msg = mock_client.messages.create.call_args_list[1].kwargs["messages"][-1]
        assert user_msg["content"][0]["is_error"] is True

    @pytest.mark.asyncio
    async def test_api_failure_skips_turn(self, agent, mock_client):
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}
        mock_client.messages.create.side_effect = RateLimitError(
            message="rate limited",
            response=mock_response,
            body=None,
        )
        with patch("agents.base.asyncio.sleep", new_callable=AsyncMock):
            result = await agent.run_turn(1)
        assert result.skipped
        assert "api_failure" in result.skip_reason

    @pytest.mark.asyncio
    async def test_empty_response_ends_turn(self, agent, mock_client):
        empty = Message(
            id="msg_test",
            content=[],
            model="claude-sonnet-4-20250514",
            role="assistant",
            stop_reason="end_turn",
            type="message",
            usage=_make_usage(),
        )
        mock_client.messages.create.return_value = empty
        result = await agent.run_turn(1)
        assert result.api_calls_made == 1
        assert result.tool_calls_made == 0

    @pytest.mark.asyncio
    async def test_soft_cap_nudge_appended_to_last_result(self, agent, mock_client):
        """Soft cap nudge is appended to last tool result content."""
        config = make_config(tool_call_soft_cap=2)
        agent = StubAgent(
            profile=make_seeker_profile(),
            config=config,
            client=mock_client,
        )
        mock_client.messages.create.side_effect = [
            _make_multi_tool_response(
                [
                    ("browse_job_board", {}, "toolu_1"),
                    ("submit_application", {"posting_id": "p1"}, "toolu_2"),
                ]
            ),
            # Post-nudge: agent makes one more call
            _make_tool_response("browse_job_board", {}, "toolu_3"),
        ]
        result = await agent.run_turn(1)
        assert result.soft_cap_hit
        # Check that the nudge was appended to the last tool result.
        # Use index [2] because mock stores a reference to the mutated
        # messages list: [0]=user, [1]=assistant, [2]=user(tool results),
        # [3]=assistant (appended after this call).
        first_followup = mock_client.messages.create.call_args_list[1]
        user_content = first_followup.kwargs["messages"][2]["content"]
        last_result = user_content[-1]
        assert "running low on time" in last_result["content"]

    @pytest.mark.asyncio
    async def test_soft_cap_allows_one_more_exchange(self, agent, mock_client):
        config = make_config(tool_call_soft_cap=1)
        agent = StubAgent(
            profile=make_seeker_profile(),
            config=config,
            client=mock_client,
        )
        mock_client.messages.create.side_effect = [
            _make_tool_response("browse_job_board", {}, "toolu_1"),
            # Post-nudge exchange
            _make_tool_response("submit_application", {"posting_id": "p1"}, "toolu_2"),
        ]
        result = await agent.run_turn(1)
        assert result.soft_cap_hit
        assert result.tool_calls_made == 2
        assert result.api_calls_made == 2

    @pytest.mark.asyncio
    async def test_soft_cap_ends_after_post_nudge(self, agent, mock_client):
        """Turn ends after one post-nudge exchange even if model wants more."""
        config = make_config(tool_call_soft_cap=1)
        agent = StubAgent(
            profile=make_seeker_profile(),
            config=config,
            client=mock_client,
        )
        mock_client.messages.create.side_effect = [
            _make_tool_response("browse_job_board", {}, "toolu_1"),
            # Post-nudge: agent tries to keep going
            _make_tool_response("submit_application", {}, "toolu_2"),
            # This should NOT be reached
            _make_text_response("still going"),
        ]
        result = await agent.run_turn(1)
        # Only 2 API calls: initial + post-nudge
        assert result.api_calls_made == 2
        assert result.soft_cap_hit

    @pytest.mark.asyncio
    async def test_usage_accumulates_across_calls(self, agent, mock_client):
        mock_client.messages.create.side_effect = [
            _make_tool_response("browse_job_board", {}),
            _make_text_response(),
        ]
        result = await agent.run_turn(1)
        # 2 calls, each with 100 input + 50 output
        assert result.total_input_tokens == 200
        assert result.total_output_tokens == 100
        assert result.total_cost > 0

    @pytest.mark.asyncio
    async def test_no_nudge_below_soft_cap(self, agent, mock_client):
        mock_client.messages.create.side_effect = [
            _make_tool_response("browse_job_board", {}, "toolu_1"),
            _make_text_response(),
        ]
        result = await agent.run_turn(1)
        assert not result.soft_cap_hit
        # Verify no nudge text was injected into the tool result message
        user_msg = mock_client.messages.create.call_args_list[1].kwargs["messages"][-1]
        assert "running low on time" not in user_msg["content"][0]["content"]

    @pytest.mark.asyncio
    async def test_notifications_passed_to_prompt(self, agent, mock_client):
        mock_client.messages.create.return_value = _make_text_response()
        await agent.run_turn(1, notifications=["Got rejected by Acme"])
        first_call = mock_client.messages.create.call_args_list[0]
        user_msg = first_call.kwargs["messages"][0]["content"]
        assert "Got rejected by Acme" in user_msg
