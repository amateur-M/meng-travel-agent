"""Tests for the conversational chat handler (P1.1, extended in V3/P1).

Tests run WITHOUT PostgreSQL (conversation_store degrades gracefully) and
WITHOUT LLM keys (conversation.py falls back to _mock_handle).
"""

import pytest
from unittest.mock import AsyncMock, patch

from agents.conversation import (
    handle_chat,
    postprocess_slots,
    postprocess_patch,
    _normalise_budget,
    _normalise_date,
    _parse_day_shift,
    _parse_day_count,
    _looks_like_modification,
    _check_ready,
    _mock_handle,
)
from schemas.chat import ChatReply


class TestPostprocessSlots:

    def test_budget_normalisation_numeric(self):
        assert _normalise_budget(5000) == 5000.0
        assert _normalise_budget("5000") == 5000.0

    def test_budget_normalisation_wan(self):
        assert _normalise_budget("1万") == 10000.0
        assert _normalise_budget("1.5万") == 15000.0

    def test_budget_normalisation_qian(self):
        assert _normalise_budget("5千") == 5000.0
        assert _normalise_budget("3千") == 3000.0

    def test_budget_normalisation_with_comma(self):
        assert _normalise_budget("5,000") == 5000.0

    def test_budget_in_postprocess(self):
        result = postprocess_slots({"budget": "5千"}, {})
        assert result["budget"] == 5000.0

    def test_date_relative_today(self):
        from datetime import date
        result = postprocess_slots({"start_date": "今天"}, {})
        assert result["start_date"] == date.today().isoformat()

    def test_date_relative_tomorrow(self):
        from datetime import date, timedelta
        result = postprocess_slots({"start_date": "明天"}, {})
        assert result["start_date"] == (date.today() + timedelta(days=1)).isoformat()

    def test_date_iso_passthrough(self):
        result = postprocess_slots({"start_date": "2026-09-01"}, {})
        assert result["start_date"] == "2026-09-01"

    def test_preferences_list(self):
        result = postprocess_slots({"preferences": ["浪漫", "美食"]}, {})
        assert result["preferences"] == ["浪漫", "美食"]

    def test_preferences_string_to_list(self):
        result = postprocess_slots({"preferences": "浪漫,美食"}, {})
        assert result["preferences"] == ["浪漫", "美食"]

    def test_pace_valid(self):
        result = postprocess_slots({"pace": "充实"}, {})
        assert result["pace"] == "充实"

    def test_pace_invalid_dropped(self):
        result = postprocess_slots({"pace": "疯狂"}, {})
        assert "pace" not in result or result.get("pace") is None

    def test_merge_with_existing(self):
        existing = {"destination": "大理", "budget": 5000.0}
        result = postprocess_slots({"start_date": "2026-09-01"}, existing)
        assert result["destination"] == "大理"
        assert result["budget"] == 5000.0
        assert result["start_date"] == "2026-09-01"

    def test_new_overrides_existing(self):
        existing = {"budget": 3000.0}
        result = postprocess_slots({"budget": "8千"}, existing)
        assert result["budget"] == 8000.0

    def test_null_does_not_clobber_existing(self):
        """LLM emits null for unmentioned fields; it must never erase collected slots."""
        existing = {
            "destination": "大理",
            "start_date": "2026-09-01",
            "end_date": "2026-09-03",
            "budget": 5000.0,
        }
        result = postprocess_slots(
            {"destination": "大理", "start_date": None, "end_date": None, "budget": None},
            existing,
        )
        assert result == existing

    def test_empty_string_does_not_clobber_existing(self):
        existing = {"destination": "大理", "budget": 5000.0}
        result = postprocess_slots({"destination": "", "budget": ""}, existing)
        assert result == existing

    def test_string_null_does_not_clobber_existing(self):
        """Some models return the string "null" instead of JSON null."""
        existing = {"destination": "大理", "start_date": "2026-09-01", "budget": 5000.0}
        result = postprocess_slots(
            {"destination": "null", "start_date": "null", "budget": "null"},
            existing,
        )
        assert result == existing

    def test_partial_turn_keeps_untouched_slots(self):
        """"想去大理"" on a session that already has dates/budget appends, not resets."""
        existing = {"start_date": "2026-09-01", "end_date": "2026-09-03", "budget": 5000.0}
        result = postprocess_slots(
            {"destination": "大理", "start_date": None, "end_date": None, "budget": None},
            existing,
        )
        assert result["destination"] == "大理"
        assert result["start_date"] == "2026-09-01"
        assert result["end_date"] == "2026-09-03"
        assert result["budget"] == 5000.0


class TestCheckReady:

    def test_all_required_present(self):
        slots = {"destination": "大理", "start_date": "2026-09-01", "end_date": "2026-09-03", "budget": 5000}
        assert _check_ready(slots) is True

    def test_missing_destination(self):
        slots = {"start_date": "2026-09-01", "end_date": "2026-09-03", "budget": 5000}
        assert _check_ready(slots) is False

    def test_missing_budget(self):
        slots = {"destination": "大理", "start_date": "2026-09-01", "end_date": "2026-09-03"}
        assert _check_ready(slots) is False

    def test_empty_slots(self):
        assert _check_ready({}) is False


class TestMockHandle:

    def test_greeting(self):
        result = _mock_handle("你好", {})
        assert result["intent"] == "greeting"
        assert "旅行" in result["reply"] or "去" in result["reply"]

    def test_question(self):
        result = _mock_handle("大理有什么好玩的？", {})
        assert result["intent"] == "question"

    def test_extract_destination(self):
        result = _mock_handle("想去大理", {})
        assert result["slots"].get("destination") == "大理"

    def test_extract_origin_from_departure_phrase(self):
        """Origin feeds the durable L2 profile, so the no-key path needs it too."""
        result = _mock_handle("我们从上海出发", {})
        assert result["slots"].get("origin") == "上海"

    def test_extract_origin_and_destination_together(self):
        result = _mock_handle("从北京去大理", {})
        assert result["slots"].get("origin") == "北京"
        assert result["slots"].get("destination") == "大理"

    def test_no_origin_without_a_departure_phrase(self):
        result = _mock_handle("想去大理", {})
        assert not result["slots"].get("origin")

    def test_extract_budget(self):
        result = _mock_handle("预算5千元", {})
        assert result["slots"].get("budget") == 5000.0

    def test_partial_slots_not_ready(self):
        result = _mock_handle("想去三亚", {})
        assert result["intent"] == "planning_intent"
        assert _check_ready(result["slots"]) is False

    def test_ready_when_all_slots(self):
        existing = {"start_date": "2026-09-01", "end_date": "2026-09-03"}
        result = _mock_handle("想去大理，预算5000元", existing)
        # mock should have destination + budget from message + dates from existing
        assert result["slots"].get("destination") == "大理"
        assert result["slots"].get("budget") == 5000.0


class TestHandleChatIntegration:

    @pytest.mark.asyncio
    async def test_greeting_returns_reply(self):
        reply = await handle_chat("你好", None)
        assert isinstance(reply, ChatReply)
        assert reply.session_id  # auto-generated
        assert reply.intent == "greeting"
        assert len(reply.reply) > 0
        assert reply.ready is False

    @pytest.mark.asyncio
    async def test_planning_intent_extracts_destination(self):
        reply = await handle_chat("想去大理", None)
        assert reply.intent in ("planning_intent", "planning_ready")
        assert reply.slots.destination == "大理"

    @pytest.mark.asyncio
    async def test_session_id_preserved(self):
        sid = "test-session-123"
        reply = await handle_chat("你好", sid)
        assert reply.session_id == sid

    @pytest.mark.asyncio
    async def test_no_500_without_postgres(self):
        """Should not raise even when the conversation store is unavailable."""
        with patch("services.conversation_store._pool_unavailable", True):
            reply = await handle_chat("嗨", None)
        assert isinstance(reply, ChatReply)
        assert reply.session_id  # still generated so the client can keep going

    @pytest.mark.asyncio
    async def test_question_does_not_change_slots(self):
        reply = await handle_chat("大理有什么好玩的？", None)
        assert reply.intent == "question"
        assert reply.ready is False
        # destination should not be set for a question
        assert reply.slots.destination is None


# ── P1.2 incremental modification ────────────────────────────────────

COMPLETE_SLOTS = {
    "destination": "大理",
    "start_date": "2026-09-01",
    "end_date": "2026-09-03",
    "budget": 5000.0,
}


class TestDayShiftParsing:
    """Unit coverage for the relative day arithmetic behind "再加一天"."""

    def test_signed_shift(self):
        assert _parse_day_shift("+1天") == 1
        assert _parse_day_shift("-1天") == -1

    def test_verbal_shift(self):
        assert _parse_day_shift("再加一天") == 1
        assert _parse_day_shift("再多两天") == 2
        assert _parse_day_shift("延长三天") == 3
        assert _parse_day_shift("提前一天") == -1

    def test_bare_duration_is_not_a_shift(self):
        assert _parse_day_shift("3天") is None
        assert _parse_day_count("3天") == 3
        assert _parse_day_count("两天") == 2

    def test_non_day_text(self):
        assert _parse_day_shift("下周末") is None
        assert _parse_day_count("大理") is None


class TestPostprocessPatch:

    def test_budget_normalisation(self):
        patch = postprocess_patch({"budget": "8千"}, COMPLETE_SLOTS)
        assert patch["budget"] == 8000.0

    def test_budget_numeric_passthrough(self):
        assert postprocess_patch({"budget": 8000}, COMPLETE_SLOTS)["budget"] == 8000.0

    def test_add_one_day_shifts_end_date(self):
        patch = postprocess_patch({"end_date": "再加一天"}, COMPLETE_SLOTS)
        assert patch["end_date"] == "2026-09-04"

    def test_day_shift_crosses_month_boundary(self):
        existing = {**COMPLETE_SLOTS, "end_date": "2026-09-30"}
        assert postprocess_patch({"end_date": "再加一天"}, existing)["end_date"] == "2026-10-01"

    def test_negative_shift_shortens_trip(self):
        patch = postprocess_patch({"end_date": "提前一天"}, COMPLETE_SLOTS)
        assert patch["end_date"] == "2026-09-02"

    def test_bare_duration_reanchors_on_start_date(self):
        patch = postprocess_patch({"end_date": "5天"}, COMPLETE_SLOTS)
        assert patch["end_date"] == "2026-09-05"

    def test_iso_date_passthrough(self):
        assert postprocess_patch({"end_date": "2026-09-05"}, COMPLETE_SLOTS)["end_date"] == "2026-09-05"

    def test_preferences_string_split(self):
        patch = postprocess_patch({"preferences": "浪漫、美食"}, COMPLETE_SLOTS)
        assert patch["preferences"] == ["浪漫", "美食"]

    def test_unknown_keys_are_dropped(self):
        assert postprocess_patch({"notes": "x"}, COMPLETE_SLOTS) == {}

    def test_null_values_dropped(self):
        assert postprocess_patch({"budget": None, "end_date": ""}, COMPLETE_SLOTS) == {}

    def test_non_dict_patch(self):
        assert postprocess_patch(None, COMPLETE_SLOTS) == {}
        assert postprocess_patch("预算加到8千", COMPLETE_SLOTS) == {}


class TestMockModify:
    """Acceptance: "预算加到8千" → budget patch; "再加一天" → end_date 推移."""

    def test_budget_increase(self):
        result = _mock_handle("预算加到8千", COMPLETE_SLOTS)
        assert result["intent"] == "modify_plan"
        assert result["modify_patch"]["budget"] == 8000.0
        assert result["slots"]["budget"] == 8000.0
        # untouched slots survive
        assert result["slots"]["destination"] == "大理"
        assert result["slots"]["end_date"] == "2026-09-03"

    def test_add_one_day(self):
        result = _mock_handle("再加一天", COMPLETE_SLOTS)
        assert result["intent"] == "modify_plan"
        assert result["modify_patch"]["end_date"] == "2026-09-04"
        assert result["slots"]["end_date"] == "2026-09-04"
        assert result["slots"]["start_date"] == "2026-09-01"

    def test_change_destination(self):
        result = _mock_handle("换成杭州", COMPLETE_SLOTS)
        assert result["intent"] == "modify_plan"
        assert result["modify_patch"]["destination"] == "杭州"
        assert result["slots"]["destination"] == "杭州"

    def test_modification_after_greeting_prefix(self):
        result = _mock_handle("你好，预算加到8千", COMPLETE_SLOTS)
        assert result["intent"] == "modify_plan"
        assert result["modify_patch"]["budget"] == 8000.0

    def test_question_style_modification(self):
        result = _mock_handle("能不能再加一天？", COMPLETE_SLOTS)
        assert result["intent"] == "modify_plan"
        assert result["modify_patch"]["end_date"] == "2026-09-04"

    def test_unrecognised_modification_asks(self):
        result = _mock_handle("改一下", COMPLETE_SLOTS)
        assert result["intent"] == "modify_plan"
        assert result["modify_patch"] is None
        assert "预算" in result["reply"]

    def test_incomplete_session_is_not_a_modification(self):
        """Without a complete plan, the same words are a fresh planning turn."""
        result = _mock_handle("预算加到8千", {})
        assert result["intent"] == "planning_intent"

    def test_ready_session_with_new_request_still_plans(self):
        result = _mock_handle("想去三亚，预算8000元", COMPLETE_SLOTS)
        assert result["intent"] == "planning_ready"


class TestLooksLikeModification:

    def test_signals(self):
        assert _looks_like_modification("预算加到8千") is True
        assert _looks_like_modification("再加一天") is True
        assert _looks_like_modification("换成杭州") is True
        assert _looks_like_modification("预算5000") is True

    def test_plain_talk(self):
        assert _looks_like_modification("你好") is False
        assert _looks_like_modification("大理有什么好玩的") is False


class TestHandleChatModify:
    """Integration: the patch is merged into session slots and ready is reset."""

    @pytest.mark.asyncio
    async def test_budget_patch_merged_and_ready_reset(self):
        with patch(
            "services.conversation_store.conversation_store.get_session",
            new=AsyncMock(return_value={"slots": dict(COMPLETE_SLOTS)}),
        ):
            reply = await handle_chat("预算加到8千", "sess-modify-budget")

        assert reply.intent == "modify_plan"
        assert reply.ready is False
        assert reply.plan_request is None
        assert reply.modify_patch is not None
        assert reply.modify_patch.budget == 8000.0
        assert reply.slots.budget == 8000.0
        assert reply.slots.destination == "大理"

    @pytest.mark.asyncio
    async def test_add_one_day_patch_merged(self):
        with patch(
            "services.conversation_store.conversation_store.get_session",
            new=AsyncMock(return_value={"slots": dict(COMPLETE_SLOTS)}),
        ):
            reply = await handle_chat("再加一天", "sess-modify-days")

        assert reply.intent == "modify_plan"
        assert reply.ready is False
        assert reply.modify_patch is not None
        assert reply.modify_patch.end_date == "2026-09-04"
        assert reply.slots.end_date == "2026-09-04"

    @pytest.mark.asyncio
    async def test_llm_patch_merged_into_slots(self):
        """The LLM path merges its modify_patch the same way the mock does."""
        llm_reply = {
            "intent": "modify_plan",
            "reply": "好的，预算调到8千～",
            "slots": {},
            "modify_patch": {"budget": "8千"},
        }
        with patch(
            "services.conversation_store.conversation_store.get_session",
            new=AsyncMock(return_value={"slots": dict(COMPLETE_SLOTS)}),
        ), patch("agents.conversation.acall_llm", new=AsyncMock(return_value=llm_reply)):
            reply = await handle_chat("预算加到8千", "sess-llm")

        assert reply.intent == "modify_plan"
        assert reply.ready is False
        assert reply.modify_patch is not None
        assert reply.modify_patch.budget == 8000.0
        assert reply.slots.budget == 8000.0
        assert reply.slots.destination == "大理"

    @pytest.mark.asyncio
    async def test_llm_day_shift_patch(self):
        llm_reply = {
            "intent": "modify_plan",
            "reply": "好的，多留一天～",
            "slots": {},
            "modify_patch": {"end_date": "再加一天"},
        }
        with patch(
            "services.conversation_store.conversation_store.get_session",
            new=AsyncMock(return_value={"slots": dict(COMPLETE_SLOTS)}),
        ), patch("agents.conversation.acall_llm", new=AsyncMock(return_value=llm_reply)):
            reply = await handle_chat("再加一天", "sess-llm-days")

        assert reply.modify_patch is not None
        assert reply.modify_patch.end_date == "2026-09-04"

    @pytest.mark.asyncio
    async def test_modify_without_patch_keeps_slots(self):
        llm_reply = {
            "intent": "modify_plan",
            "reply": "想调整哪一项？",
            "slots": {},
            "modify_patch": None,
        }
        with patch(
            "services.conversation_store.conversation_store.get_session",
            new=AsyncMock(return_value={"slots": dict(COMPLETE_SLOTS)}),
        ), patch("agents.conversation.acall_llm", new=AsyncMock(return_value=llm_reply)):
            reply = await handle_chat("改一下", "sess-no-patch")

        assert reply.intent == "modify_plan"
        assert reply.modify_patch is None
        assert reply.ready is False
        assert reply.slots.destination == "大理"
        assert reply.slots.budget == 5000.0
