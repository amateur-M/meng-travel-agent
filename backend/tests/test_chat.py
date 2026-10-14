"""Tests for the conversational chat handler (P1.1).

Tests run WITHOUT Redis (session_store degrades gracefully) and
WITHOUT LLM keys (conversation.py falls back to _mock_handle).
"""

import pytest
from unittest.mock import patch

from agents.conversation import (
    handle_chat,
    postprocess_slots,
    _normalise_budget,
    _normalise_date,
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
    async def test_no_500_without_redis(self):
        """Should not raise even when Redis is unavailable."""
        with patch("services.session_store._redis_unavailable", True):
            reply = await handle_chat("嗨", None)
        assert isinstance(reply, ChatReply)

    @pytest.mark.asyncio
    async def test_question_does_not_change_slots(self):
        reply = await handle_chat("大理有什么好玩的？", None)
        assert reply.intent == "question"
        assert reply.ready is False
        # destination should not be set for a question
        assert reply.slots.destination is None
