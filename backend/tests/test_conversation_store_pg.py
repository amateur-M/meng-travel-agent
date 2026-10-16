"""V3/P1 — real PostgreSQL round-trip for the conversation store.

These tests are the only proof that chat history *actually persists*. They are
deliberately loud when the database is unreachable: the V2 cycle shipped a
persistence layer whose tests were all green while every write silently
returned False, so a skipped verification must be visible rather than quietly
passing.
"""

import uuid

import pytest

from services.conversation_store import conversation_store


@pytest.mark.asyncio
async def test_conversation_store_round_trip():
    health = await conversation_store.health()
    if not health["connected"]:
        pytest.skip(
            "PostgreSQL unavailable — chat persistence NOT verified "
            f"(reason: {health['error']}). Run backend/scripts/init_local_db.sql."
        )

    session_id = f"pytest-{uuid.uuid4().hex}"
    client_id = f"pytest-client-{uuid.uuid4().hex}"

    try:
        # ── create ────────────────────────────────────────────────
        assert await conversation_store.ensure_session(session_id, client_id) is True
        session = await conversation_store.get_session(session_id)
        assert session is not None
        assert session["client_id"] == client_id
        assert session["slots"] == {}
        assert session["message_count"] == 0
        assert session["summary"] is None

        # ── idempotent append (recovery #6) ───────────────────────
        assert await conversation_store.append_message(
            session_id, "user", "想去大理", message_id="m1"
        ) is True
        assert await conversation_store.append_message(
            session_id, "user", "想去大理", message_id="m1"
        ) is False, "a replayed message_id must not duplicate the turn"
        assert await conversation_store.append_message(session_id, "assistant", "好呀，几天？") is True

        messages = await conversation_store.get_messages(session_id)
        assert [m["role"] for m in messages] == ["user", "assistant"]
        assert [m["content"] for m in messages] == ["想去大理", "好呀，几天？"]

        # ── L0 window ────────────────────────────────────────────
        recent = await conversation_store.get_recent_messages(session_id, limit=1)
        assert len(recent) == 1
        assert recent[0]["role"] == "assistant", "window is the most recent turns"

        session = await conversation_store.get_session(session_id)
        assert session["message_count"] == 2

        # ── slots are filtered to known fields ───────────────────
        assert await conversation_store.update_slots(
            session_id,
            {"destination": "大理", "budget": 5000.0, "junk": "dropped", "origin": None},
        ) is True
        session = await conversation_store.get_session(session_id)
        assert session["slots"] == {"destination": "大理", "budget": 5000.0}

        # ── title: first write wins, explicit rename overrides ───
        assert await conversation_store.set_title_if_empty(session_id, "大理之行") is True
        assert await conversation_store.set_title_if_empty(session_id, "不该覆盖") is False
        assert (await conversation_store.get_session(session_id))["title"] == "大理之行"
        assert await conversation_store.rename_session(session_id, "新标题") is True

        # ── L1 summary / plan link / plan request ───────────────
        assert await conversation_store.set_summary(
            session_id, "用户计划去大理三天", covered_messages=6
        ) is True
        assert await conversation_store.set_plan_request(
            session_id, {"destination": "大理", "budget": 5000}
        ) is True
        assert await conversation_store.set_last_plan(session_id, "plan-abc") is True

        session = await conversation_store.get_session(session_id)
        assert session["summary"] == "用户计划去大理三天"
        assert session["summary_message_count"] == 6, "incremental summary cursor persists"
        assert session["plan_request"]["destination"] == "大理"
        assert session["last_plan_id"] == "plan-abc"
        assert session["title"] == "新标题"

        # ── L2 profile round-trip ────────────────────────────────
        assert await conversation_store.get_profile(client_id) == {}
        assert await conversation_store.merge_profile(
            client_id, {"origin": "上海", "avoid": ["辣"]}
        ) is True
        assert await conversation_store.get_profile(client_id) == {
            "origin": "上海",
            "avoid": ["辣"],
        }
        # upsert replaces, it does not duplicate
        assert await conversation_store.merge_profile(client_id, {"origin": "上海"}) is True
        assert await conversation_store.get_profile(client_id) == {"origin": "上海"}

        # ── conversation list ────────────────────────────────────
        listed = await conversation_store.list_sessions(client_id=client_id, limit=50)
        assert [s["session_id"] for s in listed] == [session_id]
        assert listed[0]["message_count"] == 2
        assert listed[0]["preview"] == "好呀，几天？"
        assert listed[0]["last_plan_id"] == "plan-abc"

        # scoping: another client must not see it
        assert await conversation_store.list_sessions(client_id="someone-else") == []

        # ── cascade delete ───────────────────────────────────────
        assert await conversation_store.delete_session(session_id) is True
        assert await conversation_store.get_session(session_id) is None
        assert await conversation_store.get_messages(session_id) == [], "messages cascade with the session"
    finally:
        await conversation_store.delete_session(session_id)
        # the profile row is keyed by client_id, not the session — clean it too
        await conversation_store.delete_profile(client_id)


@pytest.mark.asyncio
async def test_health_reports_connected_state():
    """Whatever the environment, health() must answer without raising."""
    health = await conversation_store.health()
    assert set(health) == {"configured", "connected", "error"}
    if not health["connected"]:
        assert health["error"], "a disconnected store must explain why"
