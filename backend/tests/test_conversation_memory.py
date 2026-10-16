"""V3/P1 — conversation memory wiring tests.

These pin the behaviour that makes the agent conversational rather than
single-turn:

  * L0 memory actually reaches the model (the old handler loaded no history
    at all — ``get_history`` existed but had zero callers),
  * conversational intents get a *generated* answer instead of a canned
    deflection, while planning intents skip the second call (cost control),
  * the user's turn is persisted before the model is called, so a browser that
    dies mid-request keeps the message (recovery #5),
  * a client-supplied ``message_id`` makes the append idempotent (recovery #6).

PostgreSQL is unavailable in unit tests, so the store is mocked here. The real
round-trip lives in tests/test_conversation_store_pg.py, which skips loudly
when the database cannot be reached.
"""

import contextlib
from unittest.mock import AsyncMock, patch

import pytest

from agents.conversation import HISTORY_TURNS, handle_chat
from schemas.chat import ChatReply

TRANSCRIPT = [
    {"role": "user", "content": "我想去大理", "created_at": None},
    {"role": "assistant", "content": "好呀，打算玩几天？", "created_at": None},
]

COMPLETE_SLOTS = {
    "destination": "大理",
    "start_date": "2026-09-01",
    "end_date": "2026-09-03",
    "budget": 5000.0,
}


def store_mocks(**overrides):
    """Every ConversationStore method ``handle_chat`` touches."""
    mocks = {
        "ensure_session": AsyncMock(return_value=True),
        "get_session": AsyncMock(return_value={"slots": {}, "summary": None}),
        "get_recent_messages": AsyncMock(return_value=[]),
        "append_message": AsyncMock(return_value=True),
        "update_slots": AsyncMock(return_value=True),
        "set_title_if_empty": AsyncMock(return_value=True),
        "set_plan_request": AsyncMock(return_value=True),
    }
    mocks.update(overrides)
    return mocks


@contextlib.contextmanager
def patched_store(mocks):
    with patch.multiple("services.conversation_store.conversation_store", **mocks):
        yield mocks


def llm_reply(intent="planning_intent", reply="好的", slots=None, modify_patch=None):
    return {
        "intent": intent,
        "reply": reply,
        "slots": slots or {},
        "modify_patch": modify_patch,
    }


# ── L0: history reaches the model ────────────────────────────────────

class TestWorkingMemory:
    """The whole point of V3/P1: the model sees the conversation so far."""

    @pytest.mark.asyncio
    async def test_history_is_passed_to_intent_call(self):
        mocks = store_mocks(get_recent_messages=AsyncMock(return_value=TRANSCRIPT))
        intent_call = AsyncMock(return_value=llm_reply())

        with patched_store(mocks), patch("agents.conversation.acall_llm", new=intent_call):
            await handle_chat("三天吧", "s1")

        assert intent_call.call_args.kwargs["history"] == TRANSCRIPT

    @pytest.mark.asyncio
    async def test_history_loaded_before_the_new_turn_is_appended(self):
        """Load the window first, then append — otherwise the current message
        would appear twice in the prompt (once in history, once as the query)."""
        order = []
        mocks = store_mocks()

        async def load(*args, **kwargs):
            order.append("load_history")
            return TRANSCRIPT

        async def append(*args, **kwargs):
            order.append(f"append_{args[1]}")
            return True

        async def call(*args, **kwargs):
            order.append("llm")
            return llm_reply()

        mocks["get_recent_messages"] = AsyncMock(side_effect=load)
        mocks["append_message"] = AsyncMock(side_effect=append)

        with patched_store(mocks), patch("agents.conversation.acall_llm", new=AsyncMock(side_effect=call)):
            await handle_chat("三天吧", "s1")

        assert order == ["load_history", "append_user", "llm", "append_assistant"]

    @pytest.mark.asyncio
    async def test_history_window_is_bounded(self):
        mocks = store_mocks()
        with patched_store(mocks), patch("agents.conversation.acall_llm", new=AsyncMock(return_value=llm_reply())):
            await handle_chat("你好", "s1")
        assert mocks["get_recent_messages"].call_args.kwargs["limit"] == HISTORY_TURNS


# ── Real answers instead of a canned deflection ──────────────────────

class TestConversationalReplies:
    """`question` / `greeting` must be answered, not deflected."""

    @pytest.mark.asyncio
    async def test_question_uses_generated_answer(self):
        mocks = store_mocks()
        answer = "大理九月白天 20 度上下，早晚偏凉，环洱海骑行很舒服。"
        text_call = AsyncMock(return_value=answer)

        with patched_store(mocks), patch(
            "agents.conversation.acall_llm",
            new=AsyncMock(return_value=llm_reply(intent="question", reply="（不该出现的固定话术）")),
        ), patch("agents.conversation.acall_llm_text", new=text_call):
            reply = await handle_chat("大理九月天气怎么样？", "s1")

        assert reply.intent == "question"
        assert reply.reply == answer
        assert text_call.await_count == 1

    @pytest.mark.asyncio
    async def test_question_answer_receives_history(self):
        mocks = store_mocks(get_recent_messages=AsyncMock(return_value=TRANSCRIPT))
        text_call = AsyncMock(return_value="好的答案")

        with patched_store(mocks), patch(
            "agents.conversation.acall_llm",
            new=AsyncMock(return_value=llm_reply(intent="question")),
        ), patch("agents.conversation.acall_llm_text", new=text_call):
            await handle_chat("那边冷吗？", "s1")

        assert text_call.call_args.kwargs["history"] == TRANSCRIPT

    @pytest.mark.asyncio
    async def test_question_falls_back_when_no_api_key(self):
        """acall_llm_text returns "" without a key — the warning must not win."""
        mocks = store_mocks()
        with patched_store(mocks), patch(
            "agents.conversation.acall_llm",
            new=AsyncMock(return_value=llm_reply(intent="question", reply="固定话术兜底")),
        ), patch("agents.conversation.acall_llm_text", new=AsyncMock(return_value="")):
            reply = await handle_chat("大理好玩吗？", "s1")

        assert reply.reply == "固定话术兜底"

    @pytest.mark.asyncio
    async def test_greeting_uses_generated_answer(self):
        mocks = store_mocks()
        with patched_store(mocks), patch(
            "agents.conversation.acall_llm",
            new=AsyncMock(return_value=llm_reply(intent="greeting", reply="固定问候")),
        ), patch("agents.conversation.acall_llm_text", new=AsyncMock(return_value="生成问候")):
            reply = await handle_chat("你好", "s1")

        assert reply.intent == "greeting"
        assert reply.reply == "生成问候"

    @pytest.mark.asyncio
    async def test_planning_intent_skips_second_call(self):
        """Planning replies are templated — one LLM call per turn, not two."""
        mocks = store_mocks()
        text_call = AsyncMock(return_value="不该被调用")

        with patched_store(mocks), patch(
            "agents.conversation.acall_llm",
            new=AsyncMock(return_value=llm_reply(intent="planning_intent", reply="还差日期和预算")),
        ), patch("agents.conversation.acall_llm_text", new=text_call):
            reply = await handle_chat("想去大理", "s1")

        assert text_call.await_count == 0
        assert reply.reply == "还差日期和预算"

    @pytest.mark.asyncio
    async def test_missing_reply_falls_back_to_template(self):
        mocks = store_mocks()
        with patched_store(mocks), patch(
            "agents.conversation.acall_llm",
            new=AsyncMock(return_value=llm_reply(intent="planning_intent", reply="")),
        ):
            reply = await handle_chat("想去大理", "s1")

        assert reply.reply  # deterministic template, never empty
        assert "日期" in reply.reply or "预算" in reply.reply


# ── Persistence contract ─────────────────────────────────────────────

class TestTurnPersistence:

    @pytest.mark.asyncio
    async def test_client_message_id_is_forwarded(self):
        mocks = store_mocks()
        with patched_store(mocks), patch("agents.conversation.acall_llm", new=AsyncMock(return_value=llm_reply())):
            await handle_chat("你好", "s1", message_id="turn-abc")

        # The first append is the user's turn; the last one is the assistant's.
        user_turn = mocks["append_message"].call_args_list[0]
        assert user_turn.kwargs["message_id"] == "turn-abc"
        assert user_turn.args == ("s1", "user", "你好")

    @pytest.mark.asyncio
    async def test_server_generates_message_id_when_absent(self):
        mocks = store_mocks()
        with patched_store(mocks), patch("agents.conversation.acall_llm", new=AsyncMock(return_value=llm_reply())):
            await handle_chat("你好", "s1")

        generated = mocks["append_message"].call_args_list[0].kwargs["message_id"]
        assert generated  # a retry still has a key to deduplicate on

    @pytest.mark.asyncio
    async def test_session_is_ensured_before_use(self):
        """A stale local session_id must self-heal, not fail the foreign key."""
        mocks = store_mocks()
        with patched_store(mocks), patch("agents.conversation.acall_llm", new=AsyncMock(return_value=llm_reply())):
            await handle_chat("你好", "stale-session", client_id="client-1")

        mocks["ensure_session"].assert_awaited_once_with("stale-session", "client-1")

    @pytest.mark.asyncio
    async def test_new_session_id_generated(self):
        mocks = store_mocks()
        with patched_store(mocks), patch("agents.conversation.acall_llm", new=AsyncMock(return_value=llm_reply())):
            reply = await handle_chat("你好", None)

        assert isinstance(reply, ChatReply)
        assert reply.session_id
        assert mocks["ensure_session"].call_args.args[0] == reply.session_id

    @pytest.mark.asyncio
    async def test_assistant_reply_is_stored(self):
        mocks = store_mocks()
        with patched_store(mocks), patch(
            "agents.conversation.acall_llm", new=AsyncMock(return_value=llm_reply(reply="记住这条"))
        ):
            await handle_chat("你好", "s1")

        roles = [c.args[1] for c in mocks["append_message"].call_args_list]
        assert roles == ["user", "assistant"]
        assert mocks["append_message"].call_args_list[1].args[2] == "记住这条"

    @pytest.mark.asyncio
    async def test_slots_and_plan_request_persisted_when_ready(self):
        mocks = store_mocks(
            get_session=AsyncMock(return_value={"slots": COMPLETE_SLOTS, "summary": None})
        )
        with patched_store(mocks), patch(
            "agents.conversation.acall_llm",
            new=AsyncMock(return_value=llm_reply(intent="planning_ready", slots=COMPLETE_SLOTS)),
        ):
            reply = await handle_chat("就按这个来", "s1")

        assert reply.ready is True
        assert reply.plan_request is not None
        assert mocks["update_slots"].call_args.args[1]["destination"] == "大理"
        assert mocks["set_plan_request"].call_args.args[1]["destination"] == "大理"


# ── Titles ───────────────────────────────────────────────────────────

class TestSessionTitles:

    @pytest.mark.asyncio
    async def test_title_from_first_substantive_message(self):
        mocks = store_mocks()
        with patched_store(mocks), patch("agents.conversation.acall_llm", new=AsyncMock(return_value=llm_reply())):
            await handle_chat("想去大理玩三天，预算五千", "s1")

        assert mocks["set_title_if_empty"].call_args.args[1] == "想去大理玩三天，预算五千"

    @pytest.mark.asyncio
    async def test_title_truncated(self):
        mocks = store_mocks()
        long_message = "我" * 60
        with patched_store(mocks), patch("agents.conversation.acall_llm", new=AsyncMock(return_value=llm_reply())):
            await handle_chat(long_message, "s1")

        assert len(mocks["set_title_if_empty"].call_args.args[1]) == 20

    @pytest.mark.asyncio
    async def test_greeting_and_question_do_not_title(self):
        for intent in ("greeting", "question"):
            mocks = store_mocks()
            with patched_store(mocks), patch(
                "agents.conversation.acall_llm", new=AsyncMock(return_value=llm_reply(intent=intent))
            ), patch("agents.conversation.acall_llm_text", new=AsyncMock(return_value="答")):
                await handle_chat("你好", "s1")

            mocks["set_title_if_empty"].assert_not_awaited()


# ── Degradation ──────────────────────────────────────────────────────

class TestDegradation:

    @pytest.mark.asyncio
    async def test_intent_call_failure_degrades_to_mock(self):
        mocks = store_mocks()
        with patched_store(mocks), patch(
            "agents.conversation.acall_llm", new=AsyncMock(side_effect=RuntimeError("provider down"))
        ):
            reply = await handle_chat("想去大理", "s1")

        assert isinstance(reply, ChatReply)
        assert reply.slots.destination == "大理"  # rule-based fallback still extracts

    @pytest.mark.asyncio
    async def test_answer_call_failure_uses_fallback(self):
        mocks = store_mocks()
        with patched_store(mocks), patch(
            "agents.conversation.acall_llm",
            new=AsyncMock(return_value=llm_reply(intent="question", reply="兜底回复")),
        ), patch(
            "agents.conversation.acall_llm_text", new=AsyncMock(side_effect=RuntimeError("boom"))
        ):
            reply = await handle_chat("大理好玩吗？", "s1")

        assert reply.reply == "兜底回复"

    @pytest.mark.asyncio
    async def test_store_failure_still_answers(self):
        """Storage being down must not take the conversation down with it."""
        mocks = store_mocks(
            ensure_session=AsyncMock(return_value=False),
            get_session=AsyncMock(return_value=None),
            get_recent_messages=AsyncMock(return_value=[]),
            append_message=AsyncMock(return_value=False),
            update_slots=AsyncMock(return_value=False),
        )
        with patched_store(mocks), patch(
            "agents.conversation.acall_llm", new=AsyncMock(return_value=llm_reply(reply="照样回复"))
        ):
            reply = await handle_chat("你好", None)

        assert reply.reply == "照样回复"
