"""Chat endpoints (V4/P1: moved out of main.py).

``POST /api/chat`` plus the session CRUD that drives the sidebar and hydration.
The recall preview (``/api/chat/recall``) lives in :mod:`api.profile` because it
is an L3 memory concern rather than session management.
"""

from fastapi import APIRouter, Depends, Query, Request

from agents.conversation import handle_chat
from api.errors import not_found
from api.rate_limit import limiter
from config.settings import settings
from deps import verify_api_key
from schemas.chat import (
    ChatRequest,
    ChatReply,
    MessageListResponse,
    RenameSessionRequest,
    SessionDetail,
    SessionListResponse,
)
from services.conversation_store import conversation_store

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatReply)
@limiter.limit(settings.rate_limit_chat)
async def chat(request: Request, body: ChatRequest, _: None = Depends(verify_api_key)):
    """Conversational endpoint: intent classification + slot extraction.

    Returns a ChatReply with the assistant's text, identified intent,
    merged slots, and — when slots are complete — a plan_request that
    can be fed directly to POST /api/plan.

    The turn is persisted before the model is called and the reply after, so
    a browser that dies mid-request keeps the user's message (recovery #5),
    and a replayed ``message_id`` cannot duplicate it (recovery #6).
    """
    reply = await handle_chat(
        body.message,
        body.session_id,
        client_id=body.client_id,
        message_id=body.message_id,
    )
    return reply


@router.get("/sessions", response_model=SessionListResponse)
async def list_chat_sessions(
    client_id: str | None = Query(default=None, description="按浏览器客户端过滤"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    _: None = Depends(verify_api_key),
):
    """List conversations, most recently active first (drives the sidebar)."""
    offset = (page - 1) * size
    items = await conversation_store.list_sessions(
        client_id=client_id, limit=size, offset=offset
    )
    return {"page": page, "size": size, "items": items}


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_chat_session(
    session_id: str,
    _: None = Depends(verify_api_key),
):
    """Session metadata — used to hydrate the UI after a refresh."""
    session = await conversation_store.get_session(session_id)
    if session is None:
        raise not_found("Session not found")
    return session


@router.get("/sessions/{session_id}/messages", response_model=MessageListResponse)
async def get_chat_messages(
    session_id: str,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=200, ge=1, le=500),
    _: None = Depends(verify_api_key),
):
    """Full transcript in chronological order.

    ``total`` lets the client tell "no messages yet" apart from "session does
    not exist", which the hydrate path needs to decide whether to start a new
    conversation (recovery #4).
    """
    items = await conversation_store.get_messages(
        session_id, limit=size, offset=(page - 1) * size
    )
    session = await conversation_store.get_session(session_id)
    if session is None and not items:
        raise not_found("Session not found")
    return {
        "session_id": session_id,
        "page": page,
        "size": size,
        "total": (session or {}).get("message_count", len(items)),
        "items": items,
    }


@router.patch("/sessions/{session_id}")
async def rename_chat_session(
    session_id: str,
    body: RenameSessionRequest,
    _: None = Depends(verify_api_key),
):
    """Rename a conversation."""
    renamed = await conversation_store.rename_session(session_id, body.title.strip())
    if not renamed:
        raise not_found("Session not found")
    return {"session_id": session_id, "title": body.title.strip()}


@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    _: None = Depends(verify_api_key),
):
    """Delete a conversation and its transcript (ON DELETE CASCADE)."""
    deleted = await conversation_store.delete_session(session_id)
    if not deleted:
        raise not_found("Session not found")
    return {"session_id": session_id, "deleted": True}
