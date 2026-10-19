"""Plan endpoints (V4/P1: moved out of main.py).

Two-phase lifecycle (P0.3): ``POST /api/plan`` creates the record and launches
the graph exactly once in the background; ``GET /api/plan/{id}/stream`` consumes
the in-memory event bus, or replays the finished result from PostgreSQL when a
client reconnects after completion. Also carries history, single-plan read,
delete and activity feedback.

Route order matters: ``/history`` is registered before ``/{plan_id}`` so the
literal segment is not captured as a plan id.
"""

import asyncio

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from agents.state import AgentState
from api.errors import bad_request, not_found
from api.rate_limit import limiter
from config.settings import settings
from deps import verify_api_key
from schemas import TripPlanRequest
from services.conversation_store import conversation_store
from services.plan_pipeline import (
    _STREAM_SENTINEL,
    _run_graph_to_queue,
    plan_streams,
)
from services.sse import _sse
from services.storage import generate_plan_id, plan_store

router = APIRouter(prefix="/api/plan", tags=["plan"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.post("")
@limiter.limit(settings.rate_limit_plan)
async def create_plan(request: Request, body: TripPlanRequest, _: None = Depends(verify_api_key)):
    """Create a plan and launch the graph pipeline in the background.

    P0.3: returns JSON {plan_id, stream_url} immediately. The client
    then connects to GET /api/plan/{plan_id}/stream to consume SSE events.
    The graph runs exactly once per plan_id — reconnects to the GET
    stream do NOT re-run the pipeline.
    """
    plan_id = generate_plan_id()

    request_dict = body.model_dump(mode="json")
    # Drop the session link from the stored request body: it is conversation
    # bookkeeping, not part of the trip itself.
    request_dict.pop("session_id", None)
    # Offload: plan_store uses a sync pool, so calling it here would freeze the
    # event loop (and every other request) for the duration of the write.
    await asyncio.to_thread(plan_store.save, plan_id, request_dict, status="processing")

    # V3/P1: remember on the session which trip it produced, so the sidebar can
    # offer "查看行程" after a refresh.
    if body.session_id:
        await conversation_store.set_last_plan(body.session_id, plan_id)

    initial_state: AgentState = {
        "user_input": {
            "origin": body.origin,
            "destination": body.destination,
            "start_date": body.start_date.isoformat(),
            "end_date": body.end_date.isoformat(),
            "budget": body.budget,
            "preferences": body.preferences,
            "pace": body.pace.value,
        },
        "current_phase": "start",
        "error": "",
        "warnings": [],
    }

    # Create event queue and launch background graph task
    queue: asyncio.Queue = asyncio.Queue()
    plan_streams[plan_id] = queue
    asyncio.create_task(_run_graph_to_queue(initial_state, plan_id, queue))

    stream_url = f"/api/plan/{plan_id}/stream"
    return {
        "plan_id": plan_id,
        "stream_url": stream_url,
        "status": "processing",
    }


@router.get("/{plan_id}/stream")
async def stream_plan(plan_id: str, _: None = Depends(verify_api_key)):
    """SSE endpoint: consume events from the background graph task.

    P0.3: if the plan is already completed in PostgreSQL (e.g. client
    reconnects after the graph finished), replays the complete event
    directly. Otherwise, streams live events from the in-memory queue.
    """
    # Check if plan already completed — replay from DB
    record = await asyncio.to_thread(plan_store.get, plan_id)
    if record and record.get("status") == "completed" and record.get("response"):
        response = record["response"]
        if "plan_id" not in response:
            response["plan_id"] = plan_id

        async def _replay():
            yield _sse("complete", response)

        return StreamingResponse(_replay(), media_type="text/event-stream", headers=_SSE_HEADERS)

    if record and record.get("status") == "error":
        async def _replay_error():
            yield _sse("error", {"phase": "unknown", "message": "Plan generation failed"})

        return StreamingResponse(_replay_error(), media_type="text/event-stream", headers=_SSE_HEADERS)

    # Live stream from queue
    queue = plan_streams.get(plan_id)
    if queue is None:
        raise not_found("Stream not found. The plan may have expired.")

    async def _live_stream():
        try:
            while True:
                event = await queue.get()
                if event is _STREAM_SENTINEL:
                    break
                yield event
        except asyncio.CancelledError:
            pass
        finally:
            # Clean up the queue when the last consumer disconnects
            plan_streams.pop(plan_id, None)

    return StreamingResponse(_live_stream(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.get("/history")
async def list_plans(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    _: None = Depends(verify_api_key),
):
    """Return a paginated list of plan summaries, newest first."""
    offset = (page - 1) * size
    items = await asyncio.to_thread(plan_store.list, limit=size, offset=offset)
    return {
        "page": page,
        "size": size,
        "items": items,
    }


@router.get("/{plan_id}")
async def get_plan(plan_id: str, _: None = Depends(verify_api_key)):
    """Return a completed plan by ID (for refresh recovery)."""
    record = await asyncio.to_thread(plan_store.get, plan_id)
    if record is None:
        raise not_found("Plan not found")
    return record


@router.delete("/{plan_id}")
async def delete_plan(plan_id: str, _: None = Depends(verify_api_key)):
    """Delete a plan record."""
    deleted = await asyncio.to_thread(plan_store.delete, plan_id)
    if not deleted:
        raise not_found("Plan not found")
    return {"deleted": True, "plan_id": plan_id}


@router.post("/{plan_id}/feedback")
async def plan_feedback(plan_id: str, activity_name: str, thumbs: str, _: None = Depends(verify_api_key)):
    """Record user thumbs up/down for an activity in a completed plan.

    Query params:
        activity_name: name of the activity being rated
        thumbs: 'up' or 'down'
    """
    if thumbs not in ("up", "down"):
        raise bad_request("thumbs must be 'up' or 'down'")
    if not activity_name:
        raise bad_request("activity_name required")

    success = await asyncio.to_thread(
        plan_store.save_feedback, plan_id, activity_name, thumbs
    )
    return {"recorded": success, "plan_id": plan_id, "activity_name": activity_name, "thumbs": thumbs}
