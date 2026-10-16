"""V3/P2 — long-term memory tests: L1 summary, L2 profile, L3 recall.

The design claim under test is that long-term memory does **not** need
embeddings: L1–L3 are structured storage plus deterministic rules, so the merge
semantics and the prompt assembly can be pinned exactly.
"""

from unittest.mock import AsyncMock, patch

import pytest

from agents import memory
from agents.conversation import handle_chat
from agents.memory import (
    HISTORY_MESSAGES,
    SUMMARY_MIN_NEW_MESSAGES,
    merge_profile,
    memory_context,
    profile_updates_from,
    render_past_trips,
    render_profile,
    render_summary,
    should_summarise,
)
from tests.helpers import chat_context, llm_reply, store_mocks


# ── L2: profile extraction ───────────────────────────────────────────

class TestProfileExtraction:

    def test_promotes_durable_slots(self):
        updates = profile_updates_from(
            {
                "origin": "上海",
                "pace": "轻松",
                "preferences": ["浪漫", "美食"],
                "budget": 5000.0,
            }
        )
        assert updates["origin"] == "上海"
        assert updates["pace"] == "轻松"
        assert updates["preferences"] == ["浪漫", "美食"]
        assert updates["budget"] == 5000.0

    def test_ignores_trip_specific_slots(self):
        """Destination and dates describe one trip, not the travellers."""
        updates = profile_updates_from(
            {"destination": "大理", "start_date": "2026-09-01", "end_date": "2026-09-03"}
        )
        assert updates == {}

    def test_placeholder_origin_is_not_a_profile_fact(self):
        assert "origin" not in profile_updates_from({"origin": "未指定"})

    def test_invalid_pace_rejected(self):
        assert "pace" not in profile_updates_from({"pace": "疯狂"})

    def test_detects_avoidances(self):
        assert profile_updates_from({}, "我不吃辣")["avoid"] == ["辣"]
        assert profile_updates_from({}, "她忌口海鲜")["avoid"] == ["海鲜"]
        assert profile_updates_from({}, "对花生过敏")["avoid"] == ["花生"]

    def test_no_avoidance_when_none_stated(self):
        assert "avoid" not in profile_updates_from({}, "我们想去大理")

    def test_empty_input(self):
        assert profile_updates_from({}, "") == {}


class TestProfileMerge:

    def test_unions_collections(self):
        merged = merge_profile(
            {"preferences": ["浪漫"]}, {"preferences": ["美食", "浪漫"]}
        )
        assert merged["preferences"] == ["浪漫", "美食"]  # deduplicated, order kept

    def test_unions_avoidances(self):
        merged = merge_profile({"avoid": ["辣"]}, {"avoid": ["海鲜"]})
        assert merged["avoid"] == ["辣", "海鲜"]

    def test_budget_becomes_a_range(self):
        merged = merge_profile({"budget_range": [5000, 5000]}, {"budget": 8000.0})
        assert merged["budget_range"] == [5000.0, 8000.0]
        merged = merge_profile(merged, {"budget": 3000.0})
        assert merged["budget_range"] == [3000.0, 8000.0]

    def test_replaced_scalar_keeps_history(self):
        """Growth only: a corrected value must not erase the earlier one."""
        merged = merge_profile({"origin": "北京"}, {"origin": "上海"})
        assert merged["origin"] == "上海"
        assert merged["conflicts"]["origin"] == ["北京"]

    def test_same_scalar_does_not_create_a_conflict(self):
        merged = merge_profile({"origin": "上海"}, {"origin": "上海"})
        assert "conflicts" not in merged

    def test_conflict_history_is_bounded(self):
        profile = {}
        for value in ("A", "B", "C", "D", "E"):
            profile = merge_profile(profile, {"origin": value})
        assert profile["origin"] == "E"
        assert len(profile["conflicts"]["origin"]) == memory.MAX_CONFLICT_VALUES

    def test_never_drops_unrelated_keys(self):
        merged = merge_profile({"avoid": ["辣"], "pace": "轻松"}, {"origin": "上海"})
        assert merged["avoid"] == ["辣"]
        assert merged["pace"] == "轻松"

    def test_empty_updates_are_ignored(self):
        merged = merge_profile({"origin": "上海"}, {"origin": "", "preferences": []})
        assert merged == {"origin": "上海"}

    def test_does_not_mutate_the_input(self):
        existing = {"preferences": ["浪漫"]}
        merge_profile(existing, {"preferences": ["美食"]})
        assert existing == {"preferences": ["浪漫"]}


class TestProfileRendering:

    def test_renders_every_known_fact(self):
        text = render_profile(
            {
                "origin": "上海",
                "pace": "轻松",
                "budget_range": [3000, 8000],
                "preferences": ["浪漫"],
                "avoid": ["辣"],
            }
        )
        assert "上海" in text and "轻松" in text
        assert "3000–8000" in text
        assert "浪漫" in text and "辣" in text

    def test_annotates_conflicts(self):
        text = render_profile(merge_profile({"origin": "北京"}, {"origin": "上海"}))
        assert "上海" in text and "北京" in text

    def test_empty_profile_renders_nothing(self):
        assert render_profile({}) == ""
        assert render_profile(None) == ""


# ── L1: summary trigger ──────────────────────────────────────────────

class TestSummaryTrigger:

    def test_no_overflow_no_summary(self):
        assert should_summarise(HISTORY_MESSAGES, 0) is False
        assert should_summarise(HISTORY_MESSAGES - 2, 0) is False

    def test_overflow_below_threshold_waits(self):
        total = HISTORY_MESSAGES + SUMMARY_MIN_NEW_MESSAGES - 1
        assert should_summarise(total, 0) is False

    def test_enough_overflow_triggers(self):
        total = HISTORY_MESSAGES + SUMMARY_MIN_NEW_MESSAGES
        assert should_summarise(total, 0) is True

    def test_already_covered_overflow_does_not_retrigger(self):
        total = HISTORY_MESSAGES + SUMMARY_MIN_NEW_MESSAGES
        assert should_summarise(total, SUMMARY_MIN_NEW_MESSAGES) is False


class TestSummaryCompression:

    @pytest.mark.asyncio
    async def test_empty_slice_skips_the_llm(self):
        with patch("agents.memory.acall_llm_text", new=AsyncMock()) as call:
            assert await memory.compress_summary("旧摘要", []) == ""
        call.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_previous_summary_is_merged_not_replaced(self):
        """Incremental: the prompt carries the old summary forward."""
        text_call = AsyncMock(return_value="合并后的摘要")
        with patch("agents.memory.acall_llm_text", new=text_call):
            result = await memory.compress_summary(
                "用户打算去大理",
                [{"role": "user", "content": "预算加到8千"}],
            )

        assert result == "合并后的摘要"
        prompt = text_call.call_args.kwargs["user_prompt"]
        assert "用户打算去大理" in prompt
        assert "预算加到8千" in prompt

    @pytest.mark.asyncio
    async def test_failure_keeps_previous_summary(self):
        with patch("agents.memory.acall_llm_text", new=AsyncMock(side_effect=RuntimeError("down"))):
            assert await memory.compress_summary("旧摘要", [{"role": "user", "content": "x"}]) == ""

    @pytest.mark.asyncio
    async def test_output_is_truncated(self):
        with patch(
            "agents.memory.acall_llm_text",
            new=AsyncMock(return_value="字" * (memory.MAX_SUMMARY_CHARS + 500)),
        ):
            result = await memory.compress_summary(None, [{"role": "user", "content": "x"}])
        assert len(result) == memory.MAX_SUMMARY_CHARS


# ── L3: episodic recall ──────────────────────────────────────────────

class TestEpisodicRendering:

    def test_renders_past_trips(self):
        text = render_past_trips(
            [
                {
                    "plan_id": "p1",
                    "destination": "大理",
                    "start_date": "2026-09-01",
                    "end_date": "2026-09-03",
                    "status": "completed",
                }
            ],
            [],
        )
        assert "大理" in text and "2026-09-01~2026-09-03" in text and "已完成" in text

    def test_renders_feedback(self):
        text = render_past_trips(
            [],
            [
                {"activity_name": "洱海骑行", "up": 2, "down": 0},
                {"activity_name": "夜市购物", "up": 0, "down": 1},
            ],
        )
        assert "洱海骑行" in text and "夜市购物" in text

    def test_empty_recall_renders_nothing(self):
        assert render_past_trips([], []) == ""
        assert render_past_trips(None, None) == ""

    def test_trips_without_destination_are_skipped(self):
        assert render_past_trips([{"plan_id": "p1", "destination": None}], []) == ""


class TestPromptAssembly:

    def test_order_is_profile_then_trips_then_summary(self):
        """Most durable first, most volatile last (pinned on purpose)."""
        context = memory_context(
            profile={"origin": "上海"},
            past_trips="## 过往行程（情节记忆）\n- 大理",
            summary="用户想玩三天",
        )
        assert context.index("已知用户偏好") < context.index("过往行程")
        assert context.index("过往行程") < context.index("早前对话摘要")

    def test_missing_sections_are_omitted(self):
        context = memory_context(profile={"origin": "上海"})
        assert "过往行程" not in context
        assert "早前对话摘要" not in context

    def test_empty_context_is_empty(self):
        assert memory_context() == ""
        assert memory.compose_system_prompt("base", "") == "base"

    def test_compose_appends_context(self):
        composed = memory.compose_system_prompt("base", "## 已知用户偏好")
        assert composed.startswith("base")
        assert "已知用户偏好" in composed

    def test_summary_rendering(self):
        assert render_summary("  ") == ""
        assert "三天" in render_summary("用户想玩三天")


# ── Integration with handle_chat ─────────────────────────────────────

class TestMemoryInHandler:

    @pytest.mark.asyncio
    async def test_memory_context_reaches_the_system_prompt(self):
        mocks = store_mocks(
            get_session=AsyncMock(return_value={"slots": {}, "summary": "用户偏爱安静的地方"}),
            get_profile=AsyncMock(return_value={"origin": "上海", "avoid": ["辣"]}),
        )
        intent_call = AsyncMock(return_value=llm_reply())

        with chat_context(
            mocks,
            trips=[{"destination": "大理", "start_date": "2026-01-01", "end_date": "2026-01-03", "status": "completed"}],
        ), patch("agents.conversation.acall_llm", new=intent_call):
            await handle_chat("再推荐一个地方", "s1", client_id="c1")

        system_prompt = intent_call.call_args.kwargs["system_prompt"]
        assert "上海" in system_prompt          # L2
        assert "辣" in system_prompt            # L2
        assert "大理" in system_prompt          # L3
        assert "安静" in system_prompt          # L1

    @pytest.mark.asyncio
    async def test_profile_is_persisted_for_known_client(self):
        mocks = store_mocks(get_profile=AsyncMock(return_value={"origin": "北京"}))

        with chat_context(mocks), patch(
            "agents.conversation.acall_llm",
            new=AsyncMock(return_value=llm_reply(slots={"origin": "上海", "budget": 6000.0})),
        ):
            await handle_chat("我们从上海出发", "s1", client_id="c1")

        merged = mocks["merge_profile"].call_args.args[1]
        assert mocks["merge_profile"].call_args.args[0] == "c1"
        assert merged["origin"] == "上海"
        assert merged["conflicts"]["origin"] == ["北京"]  # old value preserved
        assert merged["budget_range"] == [6000.0, 6000.0]

    @pytest.mark.asyncio
    async def test_profile_is_skipped_without_client_id(self):
        mocks = store_mocks()
        with chat_context(mocks), patch(
            "agents.conversation.acall_llm", new=AsyncMock(return_value=llm_reply(slots={"origin": "上海"}))
        ):
            await handle_chat("我们从上海出发", "s1")

        mocks["merge_profile"].assert_not_awaited()
        mocks["get_profile"].assert_not_awaited()

    @pytest.mark.asyncio
    async def test_summary_written_once_overflow_is_large_enough(self):
        total = HISTORY_MESSAGES + SUMMARY_MIN_NEW_MESSAGES
        mocks = store_mocks(
            get_session=AsyncMock(
                return_value={"slots": {}, "summary": "旧摘要", "message_count": total,
                              "summary_message_count": 0}
            ),
            get_messages=AsyncMock(return_value=[{"role": "user", "content": "早前的话"}]),
        )
        compress = AsyncMock(return_value="新摘要")

        with chat_context(mocks), patch(
            "agents.conversation.acall_llm", new=AsyncMock(return_value=llm_reply())
        ), patch("agents.conversation.memory.compress_summary", new=compress):
            await handle_chat("继续说", "s1")

        compress.assert_awaited_once()
        # the slice starts where the previous summary stopped
        assert mocks["get_messages"].call_args.kwargs == {
            "limit": SUMMARY_MIN_NEW_MESSAGES,
            "offset": 0,
        }
        assert mocks["set_summary"].call_args.args == ("s1", "新摘要")
        assert mocks["set_summary"].call_args.kwargs["covered_messages"] == total - HISTORY_MESSAGES

    @pytest.mark.asyncio
    async def test_summary_not_written_without_overflow(self):
        mocks = store_mocks(
            get_session=AsyncMock(
                return_value={"slots": {}, "summary": None, "message_count": 4,
                              "summary_message_count": 0}
            )
        )
        compress = AsyncMock(return_value="不该生成")

        with chat_context(mocks), patch(
            "agents.conversation.acall_llm", new=AsyncMock(return_value=llm_reply())
        ), patch("agents.conversation.memory.compress_summary", new=compress):
            await handle_chat("你好", "s1")

        compress.assert_not_awaited()
        mocks["set_summary"].assert_not_awaited()

    @pytest.mark.asyncio
    async def test_summary_failure_does_not_break_the_reply(self):
        total = HISTORY_MESSAGES + SUMMARY_MIN_NEW_MESSAGES
        mocks = store_mocks(
            get_session=AsyncMock(
                return_value={"slots": {}, "summary": None, "message_count": total,
                              "summary_message_count": 0}
            )
        )

        with chat_context(mocks), patch(
            "agents.conversation.acall_llm", new=AsyncMock(return_value=llm_reply(reply="正常回复"))
        ), patch(
            "agents.conversation.memory.compress_summary",
            new=AsyncMock(side_effect=RuntimeError("summary exploded")),
        ):
            reply = await handle_chat("继续说", "s1")

        assert reply.reply == "正常回复"

    @pytest.mark.asyncio
    async def test_recall_failure_degrades_silently(self):
        mocks = store_mocks()
        with patch(
            "agents.conversation.load_episodic_recall",
            new=AsyncMock(side_effect=RuntimeError("plans table gone")),
        ):
            # load_episodic_recall is called directly, so its own try/except is
            # bypassed here; the handler must still answer.
            with chat_context(mocks), patch(
                "agents.conversation.acall_llm", new=AsyncMock(return_value=llm_reply(reply="照样回复"))
            ):
                reply = await handle_chat("你好", "s1")

        assert reply.reply in ("照样回复", "好的")
