"""Health endpoints (V4/P1: moved out of main.py)."""

import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.storage import plan_store
from services.conversation_store import conversation_store

router = APIRouter(tags=["health"])


async def _storage_state() -> tuple[bool, dict]:
    """Probe both persistence backends; return (degraded, payload)."""
    postgres = await asyncio.to_thread(plan_store.health)
    chat = await conversation_store.health()
    degraded = not postgres["connected"] or not chat["connected"]
    return degraded, {"postgres": postgres, "chat": chat}


@router.get("/health")
async def health_check():
    """Liveness probe.

    Always returns HTTP 200 so this stays a *liveness* probe (the Docker
    healthcheck and the frontend's ``depends_on: service_healthy`` rely on
    it). Read ``storage.*`` for the actual persistence state: ``status``
    becomes ``degraded`` as soon as a backend is unreachable. Use ``/ready``
    when you need a signal that actually fails on degradation.
    """
    degraded, storage = await _storage_state()
    return {
        "status": "degraded" if degraded else "ok",
        "service": "coupletrip",
        "storage": storage,
    }


@router.get("/ready")
async def readiness_check():
    """Readiness probe (P2-12): 503 while any backing store is unreachable.

    Separating readiness from liveness lets an orchestrator keep the container
    alive (it is not crashed) but pull it out of rotation until Postgres is
    reachable — something ``/health``'s always-200 contract cannot express.
    """
    degraded, storage = await _storage_state()
    payload = {
        "status": "degraded" if degraded else "ok",
        "service": "coupletrip",
        "storage": storage,
    }
    return JSONResponse(payload, status_code=503 if degraded else 200)
