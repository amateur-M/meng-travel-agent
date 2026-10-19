"""V3/P1–P3 — the full conversation path, without a database.

``test_conversation_store_pg.py`` proves persistence against a live PostgreSQL
and skips when one is not available; ``test_conversation_memory.py`` proves the
handler's wiring with the store mocked. Neither proves the *whole* path:
POST /api/chat writing a turn → the store holding it → GET .../messages reading
it back → the next turn seeing it as memory.

That path is what the user experiences, so it is driven here end-to-end through
the ASGI app against ``InMemoryConversationStore``. Only PostgreSQL, the LLM
provider and L3 recall are stubbed.

The fake store is loop-agnostic (plain dicts), so the sync ``TestClient`` tests
can seed it with ``asyncio.run`` without event-loop concerns.
"""

import asyncio
import inspect
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from agents import memory
from main import app
from services.conversation_store import ConversationStore
from tests.fake_conversation_store import InMemoryConversationStore

EPISODIC = {"trips": [], "feedback": []}


@pytest.fixture
def store():
    return InMemoryConversationStore()


@pytest.fixture
def client(store):
    """A client whose chat endpoints are backed by the in-memory store."""
    with patch("api.chat.conversation_store", store), patch(
        "api.profile.conversation_store", store
    ), patch(
        "agents.conversation.conversation_store", store
    ), patch(
        "agents.conversation.load_episodic_recall", new=AsyncMock(return_value=EPISODIC)
    ), patch(
        "api.profile.load_episodic_recall", new=AsyncMock(return_value=EPISODIC)
    ):
        yield TestClient(app)


def llm_json(intent="planning_intent", reply="好的", slots=None):
    return {
        "intent": intent,
        "reply": reply,
        "slots": slots or {},
        "modify_patch": None,
    }


def post_chat(client, message, session_id=None, message_id="m"):
    return client.post(
        "/api/chat",
        json={
            "message": message,
            "session_id": session_id,
            "client_id": "c1",
            "message_id": message_id,
        },
    )


class TestFakeParity:
    """Guard against the fake rotting away from the real interface."""

    def test_fake_matches_the_real_interface(self):
        def public(cls):
            return {
                name
                for name, _ in inspect.getmembers(cls, inspect.isfunction)
                if not name.startswith("_")
            }

        missing = public(ConversationStore) - public(InMemoryConversationStore)
        assert not missing, f"InMemoryConversationStore is missing: {sorted(missing)}"
        # Extra helpers are fine; a *missing* method is what silently breaks tests:
        # the endpoint would fall through to the real, unavailable database and
        # the test would pass for the wrong reason.

    def test_fake_reports_connected(self):
        assert asyncio.run(InMemoryConversationStore().health())["connected"] is True


class TestConversationOverHttp:
    """The user-visible loop: talk, refresh, keep talking."""

    def test_two_turns_are_persisted_in_order(self, client):
        session_id = post_chat(client, "想去大理", message_id="t1").json()["session_id"]
        post_chat(client, "玩三天吧", session_id, message_id="t2")

        transcript = client.get(f"/api/chat/sessions/{session_id}/messages").json()
        assert [m["role"] for m in transcript["items"]] == [
            "user",
            "assistant",
            "user",
            "assistant",
        ]
        assert transcript["items"][0]["content"] == "想去大理"
        assert transcript["items"][2]["content"] == "玩三天吧"
        assert transcript["total"] == 4

    def test_second_turn_receives_the_first_turn_as_memory(self, client):
        """The P1 exit criterion, proved through HTTP instead of by hand."""
        session_id = post_chat(
            client, "我们想去大理", message_id="t1"
        ).json()["session_id"]

        intent_call = AsyncMock(return_value=llm_json())
        with patch("agents.conversation.acall_llm", new=intent_call):
            post_chat(client, "三天就够了", session_id, message_id="t2")

        contents = [turn["content"] for turn in intent_call.call_args.kwargs["history"]]
        assert "我们想去大理" in contents, "turn 2 must see turn 1"
        assert "三天就够了" not in contents, "the current turn is not duplicated"

    def test_replayed_message_id_does_not_duplicate(self, client):
        session_id = post_chat(client, "想去大理", message_id="same").json()["session_id"]
        post_chat(client, "想去大理", session_id, message_id="same")

        transcript = client.get(f"/api/chat/sessions/{session_id}/messages").json()
        assert transcript["total"] == 2, transcript["items"]

    def test_slots_and_title_are_visible_after_the_turn(self, client):
        session_id = post_chat(
            client, "想去大理玩三天，预算五千", message_id="t1"
        ).json()["session_id"]

        detail = client.get(f"/api/chat/sessions/{session_id}").json()
        assert detail["title"], "a substantive message titles the conversation"

        listed = client.get("/api/chat/sessions?client_id=c1").json()["items"]
        assert [s["session_id"] for s in listed] == [session_id]
        assert listed[0]["message_count"] == 2

    def test_modify_turn_merges_into_persisted_slots(self, client, store):
        """A modify turn must land in the store, not just in the response body."""
        session_id = post_chat(client, "你好", message_id="t1").json()["session_id"]
        asyncio.run(
            store.update_slots(
                session_id,
                {
                    "destination": "大理",
                    "start_date": "2026-09-01",
                    "end_date": "2026-09-03",
                    "budget": 5000.0,
                },
            )
        )

        reply = post_chat(client, "预算加到8千", session_id, message_id="t2").json()

        assert reply["intent"] == "modify_plan"
        assert reply["modify_patch"]["budget"] == 8000.0
        sessions_slots = asyncio.run(store.get_session(session_id))["slots"]
        assert sessions_slots["budget"] == 8000.0, "modification is persisted"
        assert sessions_slots["destination"] == "大理", "untouched slots survive"

    def test_rename_and_delete_over_http(self, client):
        session_id = post_chat(client, "想去大理", message_id="t1").json()["session_id"]

        assert (
            client.patch(
                f"/api/chat/sessions/{session_id}", json={"title": "改名了"}
            ).status_code
            == 200
        )
        assert client.get(f"/api/chat/sessions/{session_id}").json()["title"] == "改名了"

        assert client.delete(f"/api/chat/sessions/{session_id}").status_code == 200
        assert client.get(f"/api/chat/sessions/{session_id}").status_code == 404
        # messages cascade with the session
        assert client.get(f"/api/chat/sessions/{session_id}/messages").status_code == 404

    def test_unknown_session_is_404_not_an_empty_conversation(self, client):
        assert client.get("/api/chat/sessions/nope").status_code == 404
        assert client.get("/api/chat/sessions/nope/messages").status_code == 404


class TestProfileOverHttp:
    """L2: what the agent learns outlives the conversation."""

    def test_profile_survives_into_a_new_conversation(self, client):
        post_chat(client, "我们从上海出发", message_id="t1")

        profile = client.get("/api/profile?client_id=c1").json()["profile"]
        assert profile["origin"] == "上海"

        # A *new* session (no session_id) must still see it in the prompt.
        intent_call = AsyncMock(return_value=llm_json())
        with patch("agents.conversation.acall_llm", new=intent_call):
            post_chat(client, "想去三亚", message_id="t2")

        assert "上海" in intent_call.call_args.kwargs["system_prompt"], (
            "L2 profile must reach a brand-new session"
        )

    def test_manual_correction_does_not_erase_what_was_learned(self, client):
        post_chat(client, "我们从北京出发", message_id="t1")
        patched = client.patch(
            "/api/profile",
            json={"client_id": "c1", "patch": {"origin": "上海", "avoid": ["辣"]}},
        ).json()["profile"]

        assert patched["origin"] == "上海"
        assert patched["conflicts"]["origin"] == ["北京"]
        assert patched["avoid"] == ["辣"]


class TestLongTermMemoryOverHttp:
    """L1/L3 through the HTTP path."""

    def test_overflowing_conversation_writes_a_rolling_summary(self, client, store):
        session_id = "long-session"
        post_chat(client, "第一句", session_id, message_id="seed-0")

        async def seed():
            for index in range(
                1, memory.HISTORY_MESSAGES + memory.SUMMARY_MIN_NEW_MESSAGES
            ):
                await store.append_message(
                    session_id, "user", f"历史消息 {index}", message_id=f"seed-{index}"
                )

        asyncio.run(seed())

        compress = AsyncMock(return_value="用户打算去大理，玩三天")
        with patch("agents.conversation.memory.compress_summary", new=compress):
            post_chat(client, "继续说", session_id, message_id="final")

        compress.assert_awaited_once()
        session = asyncio.run(store.get_session(session_id))
        assert session["summary"] == "用户打算去大理，玩三天"
        assert session["summary_message_count"] > 0, "the cursor makes L1 incremental"

    def test_summary_reaches_the_prompt_on_the_next_turn(self, client, store):
        session_id = "summarised"
        post_chat(client, "你好", session_id, message_id="t1")
        asyncio.run(store.set_summary(session_id, "用户偏爱安静的地方", covered_messages=2))

        intent_call = AsyncMock(return_value=llm_json())
        with patch("agents.conversation.acall_llm", new=intent_call):
            post_chat(client, "推荐个地方", session_id, message_id="t2")

        assert "安静" in intent_call.call_args.kwargs["system_prompt"]

    def test_recall_endpoint_reports_trips_and_feedback(self, client):
        recall = {
            "trips": [{"plan_id": "p1", "destination": "大理", "status": "completed"}],
            "feedback": [{"activity_name": "洱海骑行", "up": 1, "down": 0}],
        }
        with patch("api.profile.load_episodic_recall", new=AsyncMock(return_value=recall)):
            assert client.get("/api/chat/recall").json() == recall
