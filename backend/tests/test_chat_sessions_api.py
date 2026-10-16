"""V3/P1 — chat session management API tests.

The store is mocked: these tests pin the HTTP contract (routes, pagination,
404 semantics, argument forwarding) without needing a live database. The real
round-trip is covered separately in test_conversation_store_pg.py.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app

SESSIONS = "main.conversation_store"


@pytest.fixture
def client():
    return TestClient(app)


class TestSessionList:

    def test_returns_items_and_pagination(self, client):
        items = [
            {
                "session_id": "s1",
                "title": "大理之行",
                "updated_at": "2026-10-16T10:00:00",
                "last_plan_id": "p1",
                "message_count": 4,
                "preview": "好的，马上安排",
            }
        ]
        with patch(f"{SESSIONS}.list_sessions", new=AsyncMock(return_value=items)) as m:
            response = client.get("/api/chat/sessions?client_id=client-1&page=2&size=10")

        assert response.status_code == 200
        body = response.json()
        assert body["page"] == 2 and body["size"] == 10
        assert body["items"] == items
        # offset derived from the page
        assert m.call_args.kwargs == {"client_id": "client-1", "limit": 10, "offset": 10}

    def test_empty_list_is_not_an_error(self, client):
        with patch(f"{SESSIONS}.list_sessions", new=AsyncMock(return_value=[])):
            response = client.get("/api/chat/sessions")
        assert response.status_code == 200
        assert response.json()["items"] == []

    def test_rejects_bad_pagination(self, client):
        assert client.get("/api/chat/sessions?page=0").status_code == 422
        assert client.get("/api/chat/sessions?size=999").status_code == 422


class TestSessionDetail:

    def test_returns_session(self, client):
        session = {
            "session_id": "s1",
            "title": "大理之行",
            "summary": None,
            "slots": {"destination": "大理"},
            "plan_request": None,
            "last_plan_id": None,
            "created_at": "2026-10-16T10:00:00",
            "updated_at": "2026-10-16T10:05:00",
            "message_count": 2,
        }
        with patch(f"{SESSIONS}.get_session", new=AsyncMock(return_value=session)):
            response = client.get("/api/chat/sessions/s1")

        assert response.status_code == 200
        assert response.json()["slots"]["destination"] == "大理"

    def test_missing_session_is_404(self, client):
        """Drives the frontend's "stale pointer → start fresh" path (recovery #4)."""
        with patch(f"{SESSIONS}.get_session", new=AsyncMock(return_value=None)):
            assert client.get("/api/chat/sessions/nope").status_code == 404


class TestTranscript:

    def test_returns_messages_with_total(self, client):
        messages = [
            {"role": "user", "content": "想去大理", "created_at": None, "message_id": "m1"},
            {"role": "assistant", "content": "好呀", "created_at": None, "message_id": None},
        ]
        with patch(f"{SESSIONS}.get_messages", new=AsyncMock(return_value=messages)), patch(
            f"{SESSIONS}.get_session", new=AsyncMock(return_value={"message_count": 2})
        ):
            response = client.get("/api/chat/sessions/s1/messages")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert [m["role"] for m in body["items"]] == ["user", "assistant"]
        assert body["items"][0]["content"] == "想去大理"
        # The turn id must reach the client: after a refresh it is the only way
        # to retry a message that never got a reply without duplicating it.
        assert body["items"][0]["message_id"] == "m1"

    def test_unknown_session_is_404(self, client):
        with patch(f"{SESSIONS}.get_messages", new=AsyncMock(return_value=[])), patch(
            f"{SESSIONS}.get_session", new=AsyncMock(return_value=None)
        ):
            assert client.get("/api/chat/sessions/nope/messages").status_code == 404

    def test_known_but_empty_session_is_200(self, client):
        """A brand-new session has no messages yet — that is not a 404."""
        with patch(f"{SESSIONS}.get_messages", new=AsyncMock(return_value=[])), patch(
            f"{SESSIONS}.get_session", new=AsyncMock(return_value={"message_count": 0})
        ):
            response = client.get("/api/chat/sessions/s1/messages")

        assert response.status_code == 200
        assert response.json() == {
            "session_id": "s1",
            "page": 1,
            "size": 200,
            "total": 0,
            "items": [],
        }


class TestRename:

    def test_rename_ok(self, client):
        with patch(f"{SESSIONS}.rename_session", new=AsyncMock(return_value=True)) as m:
            response = client.patch("/api/chat/sessions/s1", json={"title": "  新标题  "})

        assert response.status_code == 200
        assert response.json()["title"] == "新标题"  # trimmed
        m.assert_awaited_once_with("s1", "新标题")

    def test_rename_missing_is_404(self, client):
        with patch(f"{SESSIONS}.rename_session", new=AsyncMock(return_value=False)):
            assert client.patch("/api/chat/sessions/nope", json={"title": "x"}).status_code == 404

    def test_empty_title_rejected(self, client):
        assert client.patch("/api/chat/sessions/s1", json={"title": ""}).status_code == 422


class TestDelete:

    def test_delete_ok(self, client):
        with patch(f"{SESSIONS}.delete_session", new=AsyncMock(return_value=True)):
            response = client.delete("/api/chat/sessions/s1")
        assert response.status_code == 200
        assert response.json()["deleted"] is True

    def test_delete_missing_is_404(self, client):
        with patch(f"{SESSIONS}.delete_session", new=AsyncMock(return_value=False)):
            assert client.delete("/api/chat/sessions/nope").status_code == 404


class TestChatForwarding:
    """POST /api/chat must pass the client identity and turn id through."""

    def test_forwards_client_id_and_message_id(self, client):
        reply = {
            "session_id": "s1",
            "reply": "好呀",
            "intent": "planning_intent",
            "slots": {},
            "ready": False,
            "plan_request": None,
            "modify_patch": None,
        }
        with patch("main.handle_chat", new=AsyncMock(return_value=reply)) as m:
            response = client.post(
                "/api/chat",
                json={
                    "message": "想去大理",
                    "session_id": "s1",
                    "client_id": "client-1",
                    "message_id": "turn-1",
                },
            )

        assert response.status_code == 200
        assert m.call_args.kwargs == {"client_id": "client-1", "message_id": "turn-1"}
        assert m.call_args.args == ("想去大理", "s1")


class TestProfileEndpoints:
    """L2 memory is readable and manually correctable (V3/P2)."""

    def test_get_profile(self, client):
        with patch(
            f"{SESSIONS}.get_profile",
            new=AsyncMock(return_value={"origin": "上海", "avoid": ["辣"]}),
        ):
            response = client.get("/api/profile?client_id=c1")

        assert response.status_code == 200
        assert response.json() == {
            "client_id": "c1",
            "profile": {"origin": "上海", "avoid": ["辣"]},
        }

    def test_get_profile_requires_a_client_id(self, client):
        assert client.get("/api/profile").status_code == 422

    def test_patch_merges_without_erasing(self, client):
        """A manual correction must not drop what the agent already learned."""
        with patch(
            f"{SESSIONS}.get_profile", new=AsyncMock(return_value={"origin": "北京"})
        ), patch(f"{SESSIONS}.merge_profile", new=AsyncMock(return_value=True)) as merged:
            response = client.patch(
                "/api/profile",
                json={"client_id": "c1", "patch": {"origin": "上海", "avoid": ["辣"]}},
            )

        assert response.status_code == 200
        stored = response.json()["profile"]
        assert stored["origin"] == "上海"
        assert stored["conflicts"]["origin"] == ["北京"]
        assert stored["avoid"] == ["辣"]
        merged.assert_awaited_once()

    def test_patch_with_no_fields_does_not_write(self, client):
        with patch(
            f"{SESSIONS}.get_profile", new=AsyncMock(return_value={"origin": "北京"})
        ), patch(f"{SESSIONS}.merge_profile", new=AsyncMock(return_value=True)) as merged:
            response = client.patch("/api/profile", json={"client_id": "c1", "patch": {}})

        assert response.status_code == 200
        assert response.json()["profile"] == {"origin": "北京"}
        merged.assert_not_awaited()

    def test_delete_profile_forgets_the_client(self, client):
        """"Forget me" removes the L2 profile only, never the conversations."""
        with patch(f"{SESSIONS}.delete_profile", new=AsyncMock(return_value=True)) as forget:
            response = client.delete("/api/profile?client_id=c1")

        assert response.status_code == 200
        assert response.json() == {"client_id": "c1", "deleted": True}
        forget.assert_awaited_once_with("c1")

    def test_delete_profile_reports_when_there_was_nothing(self, client):
        with patch(f"{SESSIONS}.delete_profile", new=AsyncMock(return_value=False)):
            response = client.delete("/api/profile?client_id=unknown")
        assert response.status_code == 200
        assert response.json()["deleted"] is False

    def test_delete_profile_requires_a_client_id(self, client):
        assert client.delete("/api/profile").status_code == 422

    def test_patch_rejects_negative_budget(self, client):
        response = client.patch(
            "/api/profile", json={"client_id": "c1", "patch": {"budget": -5}}
        )
        assert response.status_code == 422


class TestRecallEndpoint:
    """L3 episodic memory preview for the UI."""

    def test_returns_trips_and_feedback(self, client):
        recall = {
            "trips": [{"plan_id": "p1", "destination": "大理", "status": "completed"}],
            "feedback": [{"activity_name": "洱海骑行", "up": 2, "down": 0}],
        }
        with patch("main.load_episodic_recall", new=AsyncMock(return_value=recall)):
            response = client.get("/api/chat/recall")

        assert response.status_code == 200
        assert response.json() == recall

    def test_empty_recall_is_not_an_error(self, client):
        with patch(
            "main.load_episodic_recall",
            new=AsyncMock(return_value={"trips": [], "feedback": []}),
        ):
            response = client.get("/api/chat/recall")

        assert response.status_code == 200
        assert response.json() == {"trips": [], "feedback": []}


PLAN_BODY = {
    "origin": "北京",
    "destination": "大理",
    "start_date": "2026-09-01",
    "end_date": "2026-09-03",
    "budget": 5000,
    "preferences": ["浪漫", "美食"],
    "pace": "轻松",
}


class TestPlanLinksToSession:
    """A finished trip is remembered on the conversation that asked for it."""

    def test_plan_records_last_plan_on_the_session(self, client):
        with patch("main.conversation_store.set_last_plan", new=AsyncMock(return_value=True)) as link, patch(
            "main.plan_store.save", return_value=True
        ) as save, patch("main._run_graph_to_queue", new=AsyncMock()) as run:
            response = client.post("/api/plan", json={**PLAN_BODY, "session_id": "sess-1"})

        assert response.status_code == 200
        plan_id = response.json()["plan_id"]
        link.assert_awaited_once_with("sess-1", plan_id)
        # session_id is conversation bookkeeping, not part of the trip record
        assert "session_id" not in save.call_args.args[1]
        # the pipeline is still launched for that plan
        assert run.call_args.args[1] == plan_id

    def test_plan_without_session_does_not_link(self, client):
        with patch("main.conversation_store.set_last_plan", new=AsyncMock(return_value=True)) as link, patch(
            "main.plan_store.save", return_value=True
        ), patch("main._run_graph_to_queue", new=AsyncMock()):
            response = client.post("/api/plan", json=PLAN_BODY)

        assert response.status_code == 200
        link.assert_not_awaited()
