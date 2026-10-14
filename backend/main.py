"""CoupleTrip Backend — FastAPI entry point."""

import json
import asyncio
import logging
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

from schemas import TripPlanRequest, TripPlanResponse
from agents.state import AgentState
from agents.graph import graph
from services.storage import plan_store, generate_plan_id

logger = logging.getLogger("coupletrip")

app = FastAPI(
    title="CoupleTrip API",
    description="AI-powered couple travel planning agent",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ───────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "coupletrip"}


# ── SSE event helpers ───────────────────────────────────────────

def _sse(event: str, data: dict) -> str:
    """Format a single SSE event frame."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _phase_message(phase: str) -> str:
    """Map internal phase name to a human-readable progress message."""
    messages = {
        "parse_input": "正在解析您的旅行需求...",
        "fetch_weather": "正在查询目的地天气...",
        "search_poi": "正在搜索热门景点...",
        "search_food": "正在搜索本地美食...",
        "plan_itinerary": "正在为您生成行程...",
        "rhythm_control": "正在调整行程节奏...",
        "budget_check": "正在核算预算...",
        "adapt_weather": "正在根据天气调整行程...",
        "add_couple_touch": "正在添加浪漫寄语...",
        "output_format": "正在整理最终行程...",
    }
    return messages.get(phase, f"处理中: {phase}")


def _emit_node_events(phase: str, update: dict) -> list[str]:
    """Given a node's partial state update, emit targeted SSE events.

    Besides the universal `step` event, certain nodes produce richer
    payload events (partial / budget_alert / weather_swap / message)
    that let the frontend render progressively.
    """
    events: list[str] = []

    # ── step event (always) ──────────────────────────────────────
    events.append(_sse("step", {
        "phase": phase,
        "message": _phase_message(phase),
    }))

    if phase == "plan_itinerary" or phase == "rhythm_control":
        draft = update.get("draft_itinerary", {})
        for day in draft.get("days", []):
            day_index = day.get("day_index", 0)
            activities_by_period: dict[str, list] = {}
            for act in day.get("activities", []):
                period = act.get("period", "上午")
                activities_by_period.setdefault(period, []).append(act)
            events.append(_sse("partial", {
                "day_index": day_index,
                "period": "all",
                "activities": day.get("activities", []),
                "weather": day.get("weather", day.get("weather_condition", "")),
            }))

    elif phase == "budget_check":
        budget = update.get("budget_breakdown", {})
        if budget:
            events.append(_sse("budget_alert", {
                "current": budget.get("total_spent", 0),
                "limit": budget.get("total_budget", 0),
                "warning_level": budget.get("warning_level", "ok"),
                "spending_ratio": budget.get("spending_ratio", 0),
                "downgrade_applied": budget.get("downgrade_applied", False),
                "suggestions": update.get("downgrade_suggestions", []),
                "downgrade_notes": budget.get("downgrade_notes", []),
            }))

    elif phase == "adapt_weather":
        swaps = update.get("weather_swaps", [])
        for swap in swaps:
            events.append(_sse("weather_swap", {
                "day_index": swap.get("day_index", 0),
                "original": swap.get("original_name", ""),
                "replacement": swap.get("replacement_name", ""),
                "reason": swap.get("reason", ""),
                "adjustment_type": swap.get("adjustment_type", "swap"),
            }))

    elif phase == "add_couple_touch":
        draft = update.get("draft_itinerary", {})
        for day in draft.get("days", []):
            day_index = day.get("day_index", 0)
            for act in day.get("activities", []):
                note = act.get("couple_note", "")
                if note:
                    events.append(_sse("message", {
                        "day": day_index,
                        "activity": act.get("name", ""),
                        "text": note,
                    }))

    return events


# ── Plan stream bus (P0.3) ──────────────────────────────────────
# In-memory event queues keyed by plan_id. The background graph task
# puts SSE frames into the queue; GET /api/plan/{plan_id}/stream
# consumes them. When the graph completes, a sentinel None is pushed
# to signal end-of-stream.

plan_streams: dict[str, asyncio.Queue] = {}
_STREAM_SENTINEL = None  # pushed to queue when stream is done


async def _run_graph_to_queue(initial_state: dict, plan_id: str, queue: asyncio.Queue) -> None:
    """Background task: run the graph pipeline and push SSE events to *queue*.

    This is the single execution of the graph — regardless of how many
    times the client connects/reconnects to GET stream, the graph runs
    exactly once per plan_id.
    """
    try:
        final_state: dict = {}
        async for chunk in graph.astream(initial_state, stream_mode="updates"):
            if isinstance(chunk, dict):
                for node_name, update in chunk.items():
                    if not isinstance(update, dict):
                        continue
                    phase = update.get("current_phase", node_name)
                    final_state = {**final_state, **update}
                    error = update.get("error", "")
                    if error:
                        await queue.put(_sse("error", {"phase": phase, "message": error}))
                        plan_store.update(plan_id, {"error": error}, status="error")
                        await queue.put(_STREAM_SENTINEL)
                        return
                    for event in _emit_node_events(phase, update):
                        await queue.put(event)

        # ── build final result ───────────────────────────────────
        final = final_state.get("final_itinerary", {})
        warnings = final_state.get("warnings", [])
        try:
            validated = TripPlanResponse.model_validate(final)
            payload_base = validated.model_dump(mode="json")
        except Exception as val_exc:
            logger.warning("TripPlanResponse validation failed, emitting raw dict: %s", val_exc)
            payload_base = final
        payload_base["plan_id"] = plan_id
        complete_payload = {**payload_base, "warnings": warnings} if warnings else payload_base

        plan_store.update(plan_id, complete_payload, status="completed")

        await queue.put(_sse("complete", complete_payload))
        await queue.put(_STREAM_SENTINEL)

    except Exception as exc:
        logger.exception("Unhandled error in graph background task")
        plan_store.update(plan_id, {"error": str(exc)}, status="error")
        await queue.put(_sse("error", {"phase": "unknown", "message": str(exc)}))
        await queue.put(_STREAM_SENTINEL)


# ── _stream_graph kept for backward-compatible tests (P0.2) ─────

async def _stream_graph(initial_state: dict, plan_id: str) -> AsyncGenerator[str, None]:
    """Run the LangGraph pipeline and yield SSE events per node.

    Kept for test compatibility (test_sse.py calls this directly).
    Production code uses _run_graph_to_queue instead.
    """
    try:
        final_state: dict = {}
        async for chunk in graph.astream(initial_state, stream_mode="updates"):
            if isinstance(chunk, dict):
                for node_name, update in chunk.items():
                    if not isinstance(update, dict):
                        continue
                    phase = update.get("current_phase", node_name)
                    final_state = {**final_state, **update}
                    error = update.get("error", "")
                    if error:
                        yield _sse("error", {"phase": phase, "message": error})
                        plan_store.update(plan_id, {"error": error}, status="error")
                        return
                    for event in _emit_node_events(phase, update):
                        yield event
                        await asyncio.sleep(0)

        final = final_state.get("final_itinerary", {})
        warnings = final_state.get("warnings", [])
        try:
            validated = TripPlanResponse.model_validate(final)
            payload_base = validated.model_dump(mode="json")
        except Exception as val_exc:
            logger.warning("TripPlanResponse validation failed, emitting raw dict: %s", val_exc)
            payload_base = final
        payload_base["plan_id"] = plan_id
        complete_payload = {**payload_base, "warnings": warnings} if warnings else payload_base

        plan_store.update(plan_id, complete_payload, status="completed")
        yield _sse("complete", complete_payload)

    except Exception as exc:
        logger.exception("Unhandled error in SSE stream")
        plan_store.update(plan_id, {"error": str(exc)}, status="error")
        yield _sse("error", {"phase": "unknown", "message": str(exc)})


# ── Plan endpoints (P0.3: two-phase lifecycle) ─────────────────

@app.post("/api/plan")
async def create_plan(request: TripPlanRequest):
    """Create a plan and launch the graph pipeline in the background.

    P0.3: returns JSON {plan_id, stream_url} immediately. The client
    then connects to GET /api/plan/{plan_id}/stream to consume SSE events.
    The graph runs exactly once per plan_id — reconnects to the GET
    stream do NOT re-run the pipeline.
    """
    plan_id = generate_plan_id()

    request_dict = request.model_dump(mode="json")
    plan_store.save(plan_id, request_dict, status="processing")

    initial_state: AgentState = {
        "user_input": {
            "origin": request.origin,
            "destination": request.destination,
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "budget": request.budget,
            "preferences": request.preferences,
            "pace": request.pace.value,
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


@app.get("/api/plan/{plan_id}/stream")
async def stream_plan(plan_id: str):
    """SSE endpoint: consume events from the background graph task.

    P0.3: if the plan is already completed in PostgreSQL (e.g. client
    reconnects after the graph finished), replays the complete event
    directly. Otherwise, streams live events from the in-memory queue.
    """
    # Check if plan already completed — replay from DB
    record = plan_store.get(plan_id)
    if record and record.get("status") == "completed" and record.get("response"):
        response = record["response"]
        if "plan_id" not in response:
            response["plan_id"] = plan_id
        async def _replay():
            yield _sse("complete", response)
        return StreamingResponse(
            _replay(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    if record and record.get("status") == "error":
        async def _replay_error():
            yield _sse("error", {"phase": "unknown", "message": "Plan generation failed"})
        return StreamingResponse(
            _replay_error(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    # Live stream from queue
    queue = plan_streams.get(plan_id)
    if queue is None:
        return JSONResponse(status_code=404, content={"detail": "Stream not found. The plan may have expired."})

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

    return StreamingResponse(
        _live_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ── REST endpoints (P0.1) ───────────────────────────────────────

@app.get("/api/plan/history")
async def list_plans(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    """Return a paginated list of plan summaries, newest first."""
    offset = (page - 1) * size
    items = plan_store.list(limit=size, offset=offset)
    return {
        "page": page,
        "size": size,
        "items": items,
    }


@app.get("/api/plan/{plan_id}")
async def get_plan(plan_id: str):
    """Return a completed plan by ID (for refresh recovery)."""
    record = plan_store.get(plan_id)
    if record is None:
        return JSONResponse(status_code=404, content={"detail": "Plan not found"})
    return record


@app.delete("/api/plan/{plan_id}")
async def delete_plan(plan_id: str):
    """Delete a plan record."""
    deleted = plan_store.delete(plan_id)
    if not deleted:
        return JSONResponse(status_code=404, content={"detail": "Plan not found"})
    return {"deleted": True, "plan_id": plan_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
