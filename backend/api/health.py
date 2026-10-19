"""Health endpoint (V4/P1: moved out of main.py)."""

import asyncio

from fastapi import APIRouter

from services.storage import plan_store
from services.conversation_store import conversation_store

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Liveness + storage state.

    Always returns HTTP 200 so this stays a liveness probe (the Docker
    healthcheck and the frontend's ``depends_on: service_healthy`` rely on
    it). Read ``storage.*`` for the actual persistence state: ``status``
    becomes ``degraded`` as soon as a backend is unreachable.
    """
    postgres = await asyncio.to_thread(plan_store.health)
    chat = await conversation_store.health()
    degraded = not postgres["connected"] or not chat["connected"]
    return {
        "status": "degraded" if degraded else "ok",
        "service": "coupletrip",
        "storage": {
            "postgres": postgres,
            "chat": chat,
        },
    }
