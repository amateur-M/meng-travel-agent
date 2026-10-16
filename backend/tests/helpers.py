"""Shared test helpers for the conversation/memory suites.

Not a test module (no ``test_`` prefix) — it only provides the store mocks and
patchers the chat tests need, so the mock surface is declared in one place and
new store methods cannot silently fall through to the real database.
"""

import contextlib
from unittest.mock import AsyncMock, patch

from schemas.chat import ChatReply


def store_mocks(**overrides):
    """Every ConversationStore method ``handle_chat`` touches.

    Deliberately exhaustive: an unlisted method would hit the real
    (unavailable) PostgreSQL store, which passes the test for the wrong reason.
    """
    mocks = {
        "ensure_session": AsyncMock(return_value=True),
        "get_session": AsyncMock(return_value={"slots": {}, "summary": None}),
        "get_recent_messages": AsyncMock(return_value=[]),
        "append_message": AsyncMock(return_value=True),
        "update_slots": AsyncMock(return_value=True),
        "set_title_if_empty": AsyncMock(return_value=True),
        "set_plan_request": AsyncMock(return_value=True),
        "set_summary": AsyncMock(return_value=True),
        "get_profile": AsyncMock(return_value={}),
        "merge_profile": AsyncMock(return_value=True),
    }
    mocks.update(overrides)
    return mocks


@contextlib.contextmanager
def patched_store(mocks):
    with patch.multiple("services.conversation_store.conversation_store", **mocks):
        yield mocks


@contextlib.contextmanager
def patched_episodic(trips=None, feedback=None):
    """Patch L3 recall so unit tests never touch the plan tables."""
    with patch(
        "agents.conversation.load_episodic_recall",
        new=AsyncMock(return_value={"trips": trips or [], "feedback": feedback or []}),
    ):
        yield


@contextlib.contextmanager
def chat_context(mocks, trips=None, feedback=None):
    """Patch the conversation store *and* L3 recall together.

    Used by every handle_chat test so none of them accidentally reach the real
    (unavailable) PostgreSQL instance — which would pass for the wrong reason
    and pay a 5s connect timeout per process.
    """
    with patched_store(mocks), patched_episodic(trips, feedback):
        yield mocks


def llm_reply(intent="planning_intent", reply="好的", slots=None, modify_patch=None):
    """A structured Call-1 response."""
    return {
        "intent": intent,
        "reply": reply,
        "slots": slots or {},
        "modify_patch": modify_patch,
    }


__all__ = [
    "ChatReply",
    "chat_context",
    "llm_reply",
    "patched_episodic",
    "patched_store",
    "store_mocks",
]
