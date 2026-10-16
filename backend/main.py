"""CoupleTrip Backend — FastAPI entry point."""

import json
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from schemas import TripPlanRequest, TripPlanResponse
from schemas.chat import (
    ChatRequest,
    ChatReply,
    MessageListResponse,
    ProfileRequest,
    RenameSessionRequest,
    SessionDetail,
    SessionListResponse,
)
from agents.state import AgentState
from agents.graph import graph
from agents import memory
from agents.conversation import handle_chat, load_episodic_recall
from services.storage import plan_store, generate_plan_id
from services.conversation_store import conversation_store
from deps import verify_api_key
from config.settings import settings
from logging_config import configure_logging

# P3.2: 结构化日志（JSON），在 app 创建前配置以覆盖全部模块
configure_logging(json_logs=settings.json_logs)

logger = logging.getLogger("coupletrip")


# ── T0.4: Storage visibility ─────────────────────────────────────
#
# The V2 persistence layer degraded silently: with the database unreachable,
# every PlanStore call returned None/False/[] and the only trace was a
# warning, so "the feature is broken" looked identical to "nothing was
# saved yet".  Storage state is now probed once at startup and exposed on
# /health, so a misconfiguration is impossible to miss.

async def _report_storage_status() -> None:
    """Log the real connectivity of every storage backend, once, at startup."""
    pg = await asyncio.to_thread(plan_store.health)
    if pg["connected"]:
        logger.info("storage: postgres connected (plans)")
    else:
        logger.error(
            "storage: postgres UNAVAILABLE — plan persistence is DISABLED (reason: %s)",
            pg["error"],
        )

    chat = await conversation_store.health()
    if chat["connected"]:
        logger.info("storage: postgres connected (chat history)")
    else:
        logger.error(
            "storage: chat history will NOT persist (reason: %s)",
            chat["error"],
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    await _report_storage_status()
    yield


app = FastAPI(
    title="CoupleTrip API",
    description="AI-powered couple travel planning agent",
    version="0.3.0",
    lifespan=lifespan,
)

# P3.2: Prometheus metrics 暴露 /metrics
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# P3.1 限流：中间件始终挂载。RATE_LIMIT_ENABLED=false（默认）时不实际计数，
# 避免测试高频请求触发 429；生产环境设 true 开启。
limiter = Limiter(key_func=get_remote_address, enabled=settings.rate_limit_enabled)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ───────────────────────────────────────────────────────

@app.get("/health")
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


# ── Chat endpoint (P1.1) ─────────────────────────────────────────

@app.post("/api/chat", response_model=ChatReply)
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


# ── Chat session management (V3/P1) ──────────────────────────────

@app.get("/api/chat/sessions", response_model=SessionListResponse)
async def list_chat_sessions(
    client_id: Optional[str] = Query(default=None, description="按浏览器客户端过滤"),
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


@app.get("/api/chat/sessions/{session_id}", response_model=SessionDetail)
async def get_chat_session(
    session_id: str,
    _: None = Depends(verify_api_key),
):
    """Session metadata — used to hydrate the UI after a refresh."""
    session = await conversation_store.get_session(session_id)
    if session is None:
        return JSONResponse(status_code=404, content={"detail": "Session not found"})
    return session


@app.get("/api/chat/sessions/{session_id}/messages", response_model=MessageListResponse)
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
        return JSONResponse(status_code=404, content={"detail": "Session not found"})
    return {
        "session_id": session_id,
        "page": page,
        "size": size,
        "total": (session or {}).get("message_count", len(items)),
        "items": items,
    }


@app.patch("/api/chat/sessions/{session_id}")
async def rename_chat_session(
    session_id: str,
    body: RenameSessionRequest,
    _: None = Depends(verify_api_key),
):
    """Rename a conversation."""
    renamed = await conversation_store.rename_session(session_id, body.title.strip())
    if not renamed:
        return JSONResponse(status_code=404, content={"detail": "Session not found"})
    return {"session_id": session_id, "title": body.title.strip()}


@app.delete("/api/chat/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    _: None = Depends(verify_api_key),
):
    """Delete a conversation and its transcript (ON DELETE CASCADE)."""
    deleted = await conversation_store.delete_session(session_id)
    if not deleted:
        return JSONResponse(status_code=404, content={"detail": "Session not found"})
    return {"session_id": session_id, "deleted": True}


# ── Memory: profile (L2) and recall (L3) ─────────────────────────

@app.get("/api/profile")
async def get_profile(
    client_id: str = Query(..., min_length=1, max_length=64),
    _: None = Depends(verify_api_key),
):
    """Return the durable cross-session profile for this browser."""
    profile = await conversation_store.get_profile(client_id)
    return {"client_id": client_id, "profile": profile}


@app.patch("/api/profile")
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


@app.get("/api/chat/recall")
async def get_recall(_: None = Depends(verify_api_key)):
    """Episodic memory preview (L3) for the UI: past trips + activity feedback."""
    return await load_episodic_recall()


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
        degraded = bool(warnings)
        complete_payload = {**payload_base, "warnings": warnings, "degraded": degraded} if warnings else {**payload_base, "degraded": degraded}

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
        degraded = bool(warnings)
        complete_payload = {**payload_base, "warnings": warnings, "degraded": degraded} if warnings else {**payload_base, "degraded": degraded}

        plan_store.update(plan_id, complete_payload, status="completed")
        yield _sse("complete", complete_payload)

    except Exception as exc:
        logger.exception("Unhandled error in SSE stream")
        plan_store.update(plan_id, {"error": str(exc)}, status="error")
        yield _sse("error", {"phase": "unknown", "message": str(exc)})


# ── Plan endpoints (P0.3: two-phase lifecycle) ─────────────────

@app.post("/api/plan")
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
    plan_store.save(plan_id, request_dict, status="processing")

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


@app.get("/api/plan/{plan_id}/stream")
async def stream_plan(plan_id: str, _: None = Depends(verify_api_key)):
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
    _: None = Depends(verify_api_key),
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
async def get_plan(plan_id: str, _: None = Depends(verify_api_key)):
    """Return a completed plan by ID (for refresh recovery)."""
    record = plan_store.get(plan_id)
    if record is None:
        return JSONResponse(status_code=404, content={"detail": "Plan not found"})
    return record


@app.delete("/api/plan/{plan_id}")
async def delete_plan(plan_id: str, _: None = Depends(verify_api_key)):
    """Delete a plan record."""
    deleted = plan_store.delete(plan_id)
    if not deleted:
        return JSONResponse(status_code=404, content={"detail": "Plan not found"})
    return {"deleted": True, "plan_id": plan_id}


# ── Feedback endpoint (P2.3) ────────────────────────────────────

@app.post("/api/plan/{plan_id}/feedback")
async def plan_feedback(plan_id: str, activity_name: str, thumbs: str, _: None = Depends(verify_api_key)):
    """Record user thumbs up/down for an activity in a completed plan.

    Query params:
        activity_name: name of the activity being rated
        thumbs: 'up' or 'down'
    """
    if thumbs not in ("up", "down"):
        return JSONResponse(status_code=400, content={"detail": "thumbs must be 'up' or 'down'"})
    if not activity_name:
        return JSONResponse(status_code=400, content={"detail": "activity_name required"})

    success = plan_store.save_feedback(plan_id, activity_name, thumbs)
    return {"recorded": success, "plan_id": plan_id, "activity_name": activity_name, "thumbs": thumbs}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
