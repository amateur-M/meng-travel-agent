"""In-memory stand-in for ``ConversationStore`` (PostgreSQL-free).

The real store's round-trip is verified against a live database in
``test_conversation_store_pg.py``, which skips when PostgreSQL is unavailable.
That left the *full HTTP path* — POST /api/chat writing a turn, then
GET /api/chat/sessions/{id}/messages reading it back, with memory carried
across turns — provable only by hand.

This fake mirrors the real store's observable semantics closely enough to
drive that path in tests: idempotent appends, cascade deletes, the summary
cursor, slot filtering and the profile merge target.

``test_conversation_e2e.py::test_fake_matches_the_real_interface`` asserts this
class still implements every public method of the real store, so interface
drift fails the suite instead of silently passing.
"""

import uuid

from services.conversation_store import _SLOT_FIELDS


class InMemoryConversationStore:
    """Same public surface as ``ConversationStore``, backed by dicts."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict] = {}
        self.messages: dict[str, list[dict]] = {}
        self.profiles: dict[str, dict] = {}
        self._clock = 0

    # ── helpers ───────────────────────────────────────────────────

    def _tick(self) -> str:
        self._clock += 1
        return f"2026-01-01T00:00:00.{self._clock:06d}"

    def _touch(self, session_id: str) -> None:
        if session_id in self.sessions:
            self.sessions[session_id]["updated_at"] = self._tick()

    # ── sessions ──────────────────────────────────────────────────

    async def ensure_session(self, session_id: str, client_id=None) -> bool:
        if session_id not in self.sessions:
            stamp = self._tick()
            self.sessions[session_id] = {
                "session_id": session_id,
                "title": None,
                "summary": None,
                "summary_message_count": 0,
                "slots": {},
                "plan_request": None,
                "last_plan_id": None,
                "client_id": client_id,
                "created_at": stamp,
                "updated_at": stamp,
            }
            self.messages[session_id] = []
        return True

    async def get_session(self, session_id: str):
        session = self.sessions.get(session_id)
        if session is None:
            return None
        return {**session, "message_count": len(self.messages.get(session_id, []))}

    async def list_sessions(self, client_id=None, limit=20, offset=0) -> list[dict]:
        rows = [
            s
            for s in self.sessions.values()
            if client_id is None or s["client_id"] == client_id
        ]
        rows.sort(key=lambda s: s["updated_at"], reverse=True)
        out = []
        for session in rows[offset : offset + limit]:
            messages = self.messages.get(session["session_id"], [])
            out.append(
                {
                    "session_id": session["session_id"],
                    "title": session["title"],
                    "updated_at": session["updated_at"],
                    "last_plan_id": session["last_plan_id"],
                    "message_count": len(messages),
                    "preview": (messages[-1]["content"][:80] if messages else ""),
                }
            )
        return out

    async def rename_session(self, session_id: str, title: str) -> bool:
        if session_id not in self.sessions:
            return False
        self.sessions[session_id]["title"] = title
        return True

    async def set_title_if_empty(self, session_id: str, title: str) -> bool:
        session = self.sessions.get(session_id)
        if session is None or session["title"]:
            return False
        session["title"] = title
        return True

    async def delete_session(self, session_id: str) -> bool:
        if session_id not in self.sessions:
            return False
        del self.sessions[session_id]
        self.messages.pop(session_id, None)
        return True

    # ── messages ──────────────────────────────────────────────────

    async def append_message(
        self, session_id: str, role: str, content: str, message_id=None
    ) -> bool:
        if session_id not in self.sessions:
            return False
        rows = self.messages.setdefault(session_id, [])
        if message_id and any(m["message_id"] == message_id for m in rows):
            return False  # ON CONFLICT DO NOTHING
        rows.append(
            {
                "role": role,
                "content": content,
                "message_id": message_id,
                "created_at": self._tick(),
            }
        )
        self._touch(session_id)
        return True

    async def get_messages(self, session_id: str, limit=200, offset=0) -> list[dict]:
        return [
            {
                "role": m["role"],
                "content": m["content"],
                "created_at": m["created_at"],
                "message_id": m["message_id"],
            }
            for m in self.messages.get(session_id, [])[offset : offset + limit]
        ]

    async def get_recent_messages(self, session_id: str, limit=10) -> list[dict]:
        rows = self.messages.get(session_id, [])[-limit:] if limit else []
        return [
            {"role": m["role"], "content": m["content"], "created_at": m["created_at"]}
            for m in rows
        ]

    # ── session state ─────────────────────────────────────────────

    async def update_slots(self, session_id: str, slots: dict) -> bool:
        if session_id not in self.sessions:
            return False
        self.sessions[session_id]["slots"] = {
            k: v for k, v in slots.items() if k in _SLOT_FIELDS and v is not None
        }
        self._touch(session_id)
        return True

    async def set_plan_request(self, session_id: str, plan_request) -> bool:
        if session_id not in self.sessions:
            return False
        self.sessions[session_id]["plan_request"] = plan_request
        return True

    async def set_summary(
        self, session_id: str, summary, covered_messages=None
    ) -> bool:
        session = self.sessions.get(session_id)
        if session is None:
            return False
        session["summary"] = summary
        if covered_messages is not None:
            session["summary_message_count"] = covered_messages
        return True

    async def set_last_plan(self, session_id: str, plan_id: str) -> bool:
        if session_id not in self.sessions:
            return False
        self.sessions[session_id]["last_plan_id"] = plan_id
        return True

    # ── profiles ──────────────────────────────────────────────────

    async def get_profile(self, client_id: str) -> dict:
        return self.profiles.get(client_id, {})

    async def merge_profile(self, client_id: str, merged_profile: dict) -> bool:
        if not client_id:
            return False
        self.profiles[client_id] = merged_profile or {}
        return True

    async def delete_profile(self, client_id: str) -> bool:
        return self.profiles.pop(client_id, None) is not None

    # ── health ────────────────────────────────────────────────────

    async def health(self) -> dict:
        return {"configured": True, "connected": True, "error": None}


def new_session_id() -> str:
    return f"fake-{uuid.uuid4().hex}"
