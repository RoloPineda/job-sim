"""Tests for the prompt builder module."""

import pytest

from src.engine.prompt_builder import PromptBuilder
from src.schemas.agents import AgentProfile, HiringManagerProfile, RecruiterProfile
from src.schemas.config import RunConfig
from tests.helpers import (
    make_config,
    make_hm_profile,
    make_recruiter_profile,
    make_sample_tools,
    make_seeker_profile,
)


@pytest.fixture()
def config() -> RunConfig:
    return make_config()


@pytest.fixture()
def builder(config) -> PromptBuilder:
    return PromptBuilder(config)


@pytest.fixture()
def seeker_profile() -> AgentProfile:
    return make_seeker_profile()


@pytest.fixture()
def recruiter_profile() -> RecruiterProfile:
    return make_recruiter_profile()


@pytest.fixture()
def hm_profile() -> HiringManagerProfile:
    return make_hm_profile()


@pytest.fixture()
def sample_tools() -> list[dict]:
    return make_sample_tools()


class TestBuildSystemMessage:
    def test_seeker_contains_identity(self, builder, seeker_profile):
        msg = builder.build_system_message(seeker_profile)
        assert "Sarah Chen" in msg
        assert "Austin, TX" in msg
        assert "a professional" in msg

    def test_disposition_before_backstory(self, builder, seeker_profile):
        msg = builder.build_system_message(seeker_profile)
        disp_pos = msg.index("Methodical")
        backstory_pos = msg.index("Spent 5 years")
        assert disp_pos < backstory_pos

    def test_recruiter_role_label(self, builder, recruiter_profile):
        msg = builder.build_system_message(recruiter_profile)
        assert "a recruiter" in msg
        assert "James Park" in msg

    def test_hm_role_label(self, builder, hm_profile):
        msg = builder.build_system_message(hm_profile)
        assert "a hiring manager" in msg
        assert "Dana Reeves" in msg

    def test_no_simulation_language(self, builder, seeker_profile):
        msg = builder.build_system_message(seeker_profile)
        lower = msg.lower()
        for forbidden in (
            "simulation",
            "candor",
            "ai agent",
            "llm",
            "round-based",
        ):
            assert forbidden not in lower

    def test_seeker_instructions_not_prescriptive_on_communication(
        self, builder, seeker_profile
    ):
        msg = builder.build_system_message(seeker_profile)
        assert "authentic" in msg

    def test_recruiter_instructions_not_prescriptive_on_responsiveness(
        self, builder, recruiter_profile
    ):
        msg = builder.build_system_message(recruiter_profile)
        assert "regardless of the outcome" not in msg

    def test_hm_instructions_not_prescriptive_on_feedback_clarity(
        self, builder, hm_profile
    ):
        msg = builder.build_system_message(hm_profile)
        assert "vague direction" not in msg


class TestBuildUserMessage:
    def test_includes_round_number(self, builder):
        msg = builder.build_user_message("some context", 7, "job_seeker")
        assert "Current round: 7" in msg

    def test_includes_context(self, builder):
        msg = builder.build_user_message("pipeline status here", 1, "recruiter")
        assert "pipeline status here" in msg

    def test_seeker_closing(self, builder):
        msg = builder.build_user_message("ctx", 1, "job_seeker")
        assert msg.endswith("What would you like to do?")

    def test_recruiter_closing(self, builder):
        msg = builder.build_user_message("ctx", 1, "recruiter")
        assert msg.endswith("How would you like to proceed?")

    def test_hm_closing(self, builder):
        msg = builder.build_user_message("ctx", 1, "hiring_manager")
        assert msg.endswith("How would you like to proceed?")

    def test_with_notifications(self, builder):
        msg = builder.build_user_message(
            "ctx",
            3,
            "job_seeker",
            ["Rejected by Acme Corp", "Interview at TechCo"],
        )
        assert "Recent updates:" in msg
        assert "- Rejected by Acme Corp" in msg
        assert "- Interview at TechCo" in msg

    def test_no_notifications_section_when_empty(self, builder):
        msg = builder.build_user_message("ctx", 3, "job_seeker")
        assert "Recent updates:" not in msg

    def test_no_notifications_section_when_none(self, builder):
        msg = builder.build_user_message("ctx", 3, "job_seeker", None)
        assert "Recent updates:" not in msg


class TestFormatTools:
    def test_passes_valid_tools(self, builder, sample_tools):
        result = builder.format_tools(sample_tools)
        assert len(result) == 2
        assert result[0]["name"] == "browse_job_board"
        assert result[1]["name"] == "submit_application"

    def test_strips_extra_keys(self, builder):
        tools = [
            {
                "name": "test_tool",
                "description": "A test.",
                "input_schema": {"type": "object", "properties": {}},
                "extra_field": "should be dropped",
            }
        ]
        result = builder.format_tools(tools)
        assert "extra_field" not in result[0]

    def test_raises_on_missing_name(self, builder):
        tools = [{"description": "No name.", "input_schema": {}}]
        with pytest.raises(ValueError, match="name"):
            builder.format_tools(tools)

    def test_raises_on_missing_description(self, builder):
        tools = [{"name": "t", "input_schema": {}}]
        with pytest.raises(ValueError, match="description"):
            builder.format_tools(tools)

    def test_raises_on_missing_input_schema(self, builder):
        tools = [{"name": "t", "description": "d"}]
        with pytest.raises(ValueError, match="input_schema"):
            builder.format_tools(tools)

    def test_empty_list_returns_empty(self, builder):
        assert builder.format_tools([]) == []


class TestBuildActionPayload:
    def test_assembles_all_pieces(self, builder, seeker_profile, sample_tools):
        payload = builder.build_action_payload(
            seeker_profile, "my context", 5, sample_tools
        )
        assert "Sarah Chen" in payload["system"]
        assert "Current round: 5" in payload["messages"][0]["content"]
        assert len(payload["tools"]) == 2

    def test_omits_tools_key_when_empty(self, builder, seeker_profile):
        payload = builder.build_action_payload(seeker_profile, "ctx", 1, [])
        assert "tools" not in payload

    def test_includes_notifications(self, builder, seeker_profile, sample_tools):
        payload = builder.build_action_payload(
            seeker_profile,
            "ctx",
            2,
            sample_tools,
            notifications=["Got a callback"],
        )
        assert "Got a callback" in payload["messages"][0]["content"]


class TestMergeConsecutiveRoles:
    def test_single_message_unchanged(self):
        msgs = [{"role": "user", "content": "hello"}]
        result = PromptBuilder._merge_consecutive_roles(msgs)
        assert result == msgs

    def test_alternating_roles_unchanged(self):
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "bye"},
        ]
        result = PromptBuilder._merge_consecutive_roles(msgs)
        assert len(result) == 3

    def test_two_consecutive_user_merged(self):
        msgs = [
            {"role": "user", "content": "first"},
            {"role": "user", "content": "second"},
        ]
        result = PromptBuilder._merge_consecutive_roles(msgs)
        assert len(result) == 1
        assert "first" in result[0]["content"]
        assert "second" in result[0]["content"]

    def test_three_consecutive_same_role_merged(self):
        msgs = [
            {"role": "user", "content": "a"},
            {"role": "user", "content": "b"},
            {"role": "user", "content": "c"},
        ]
        result = PromptBuilder._merge_consecutive_roles(msgs)
        assert len(result) == 1
        assert result[0]["content"] == "a\n\nb\n\nc"

    def test_mixed_consecutive_groups(self):
        msgs = [
            {"role": "user", "content": "u1"},
            {"role": "user", "content": "u2"},
            {"role": "assistant", "content": "a1"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "u3"},
        ]
        result = PromptBuilder._merge_consecutive_roles(msgs)
        assert len(result) == 3
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
        assert result[2]["role"] == "user"


class TestBuildInterviewTurn:
    def test_empty_transcript_first_turn(self, builder, seeker_profile):
        payload = builder.build_interview_turn(
            seeker_profile,
            "Interviewing for Senior Engineer at TechCo.",
            [],
            1,
        )
        assert len(payload["messages"]) == 1
        assert payload["messages"][0]["role"] == "user"
        assert "Senior Engineer" in payload["messages"][0]["content"]

    def test_no_tools_in_interview(self, builder, seeker_profile):
        payload = builder.build_interview_turn(seeker_profile, "context", [], 1)
        assert "tools" not in payload

    def test_transcript_role_mapping_with_merge(self, builder, seeker_profile):
        transcript = [
            {"speaker": "Dana Reeves", "content": "Tell me about yourself."},
            {"speaker": "Sarah Chen", "content": "I have 5 years of experience."},
            {"speaker": "Dana Reeves", "content": "What's your biggest strength?"},
        ]
        payload = builder.build_interview_turn(
            seeker_profile, "Interview context.", transcript, 4
        )
        messages = payload["messages"]
        # role_context + Dana's first message merge into one user msg
        assert messages[0]["role"] == "user"
        assert "Interview context." in messages[0]["content"]
        assert "Tell me about yourself." in messages[0]["content"]
        # Sarah's response as assistant
        assert messages[1]["role"] == "assistant"
        assert "5 years" in messages[1]["content"]
        # Dana's follow-up as user
        assert messages[2]["role"] == "user"

    def test_consecutive_same_speaker_merged(self, builder, seeker_profile):
        transcript = [
            {"speaker": "Dana Reeves", "content": "First question."},
            {"speaker": "Dana Reeves", "content": "Actually, let me rephrase."},
        ]
        payload = builder.build_interview_turn(
            seeker_profile, "Interview context.", transcript, 2
        )
        messages = payload["messages"]
        assert len(messages) == 1
        assert "First question." in messages[0]["content"]
        assert "let me rephrase" in messages[0]["content"]

    def test_appends_continue_when_transcript_ends_on_speaker(
        self, builder, seeker_profile
    ):
        transcript = [
            {"speaker": "Dana Reeves", "content": "Tell me about yourself."},
            {"speaker": "Sarah Chen", "content": "I have 5 years of experience."},
        ]
        payload = builder.build_interview_turn(seeker_profile, "context", transcript, 2)
        assert payload["messages"][-1]["role"] == "user"
        assert "Please continue" in payload["messages"][-1]["content"]

    def test_no_continue_when_transcript_ends_on_other(self, builder, seeker_profile):
        transcript = [
            {"speaker": "Dana Reeves", "content": "Tell me about yourself."},
        ]
        payload = builder.build_interview_turn(seeker_profile, "context", transcript, 2)
        assert payload["messages"][-1]["role"] == "user"
        assert "Please continue" not in payload["messages"][-1]["content"]

    def test_wrap_up_cue_at_ceiling_minus_one(self, builder, seeker_profile):
        payload = builder.build_interview_turn(
            seeker_profile,
            "context",
            [{"speaker": "Dana Reeves", "content": "Last question."}],
            5,
        )
        assert "wrapping up" in payload["messages"][-1]["content"]

    def test_no_wrap_up_before_ceiling(self, builder, seeker_profile):
        payload = builder.build_interview_turn(
            seeker_profile,
            "context",
            [{"speaker": "Dana Reeves", "content": "A question."}],
            3,
        )
        assert "wrapping up" not in payload["messages"][-1]["content"]

    def test_wrap_up_at_ceiling(self, builder, seeker_profile):
        payload = builder.build_interview_turn(
            seeker_profile,
            "context",
            [{"speaker": "Dana Reeves", "content": "Final."}],
            6,
        )
        assert "wrapping up" in payload["messages"][-1]["content"]


class TestBuildReflectionPrompt:
    def test_includes_context_summary(self, builder, seeker_profile):
        payload = builder.build_reflection_prompt(
            seeker_profile, "Applied to 12 jobs, ghosted 8 times."
        )
        assert "ghosted 8 times" in payload["messages"][0]["content"]

    def test_includes_reflection_question(self, builder, seeker_profile):
        payload = builder.build_reflection_prompt(seeker_profile, "summary")
        content = payload["messages"][0]["content"]
        assert "reflect" in content.lower()
        assert "What's working" in content

    def test_no_tools_in_reflection(self, builder, seeker_profile):
        payload = builder.build_reflection_prompt(seeker_profile, "summary")
        assert "tools" not in payload

    def test_system_matches_profile(self, builder, recruiter_profile):
        payload = builder.build_reflection_prompt(recruiter_profile, "summary")
        assert "James Park" in payload["system"]
