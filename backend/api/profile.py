"""Memory endpoints (V4/P1: moved out of main.py).

L2 cross-session profile (read / correct / forget) and the L3 episodic recall
preview. The recall route keeps its ``/api/chat/recall`` path even though it
lives here, so the router carries full paths rather than a single prefix.
"""

from fastapi import APIRouter, Depends, Query

from agents import memory
from agents.conversation import load_episodic_recall
from deps import verify_api_key
from schemas.chat import ProfileRequest
from services.conversation_store import conversation_store

router = APIRouter(tags=["memory"])


@router.get("/api/profile")
async def get_profile(
    client_id: str = Query(..., min_length=1, max_length=64),
    _: None = Depends(verify_api_key),
):
    """Return the durable cross-session profile for this browser."""
    profile = await conversation_store.get_profile(client_id)
    return {"client_id": client_id, "profile": profile}


@router.patch("/api/profile")
async def update_profile(
    body: ProfileRequest,
    _: None = Depends(verify_api_key),
):
    """Manually correct the profile ("记住我不吃辣").

    Uses the same merge rules as automatic extraction, so a manual entry can
    never silently erase what the agent already learned.
    """
    current = await conversation_store.get_profile(body.client_id)
    updates = {
        k: v
        for k, v in body.patch.model_dump().items()
        if v is not None and v != [] and v != ""
    }
    merged = memory.merge_profile(current, updates)
    if updates:
        await conversation_store.merge_profile(body.client_id, merged)
    return {"client_id": body.client_id, "profile": merged}


@router.delete("/api/profile")
async def forget_profile(
    client_id: str = Query(..., min_length=1, max_length=64),
    _: None = Depends(verify_api_key),
):
    """Forget everything remembered about this browser (the "forget me" action).

    Removes the L2 profile row only. Conversations are separate objects that the
    user deletes individually, so this never silently wipes their history.
    """
    deleted = await conversation_store.delete_profile(client_id)
    return {"client_id": client_id, "deleted": deleted}


@router.get("/api/chat/recall")
async def get_recall(_: None = Depends(verify_api_key)):
    """Episodic memory preview (L3) for the UI: past trips + activity feedback."""
    return await load_episodic_recall()
