"""CoupleTrip Backend — FastAPI entry point."""

import json
import asyncio
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from schemas import TripPlanRequest
from agents.state import AgentState
from agents.graph import graph

app = FastAPI(
    title="CoupleTrip API",
    description="AI-powered couple travel planning agent",
    version="0.1.0",
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


# ── Plan (SSE streaming) ────────────────────────────────────────

async def _stream_graph(initial_state: dict) -> AsyncGenerator[str, None]:
    """Run the LangGraph pipeline and yield SSE events per node.

    Uses graph.astream() for async-friendly per-node state snapshots.
    Falls back to a blocking graph.stream() wrapped in a thread if
    astream is unavailable (older LangGraph versions).
    """
    try:
        async for chunk in graph.astream(initial_state, stream_mode="values"):
            phase = chunk.get("current_phase", "")
            error = chunk.get("error", "")

            if error:
                yield f"event: error\ndata: {json.dumps({'phase': phase, 'message': error}, ensure_ascii=False)}\n\n"
                return

            # Build a lightweight progress event
            payload = {
                "phase": phase,
                "message": _phase_message(phase),
            }
            yield f"event: step\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0)  # yield control to event loop

        # ── emit final result ────────────────────────────────────
        final_state = await graph.ainvoke(initial_state)
        final = final_state.get("final_itinerary", {})
        yield f"event: complete\ndata: {json.dumps(final, ensure_ascii=False)}\n\n"

    except AttributeError:
        # Fallback: graph.stream() is sync-only in older LangGraph
        import concurrent.futures

        def _run_sync():
            events = []
            for chunk in graph.stream(initial_state, stream_mode="values"):
                events.append(chunk)
            final = graph.invoke(initial_state)
            events.append(final)
            return events

        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            events = await loop.run_in_executor(pool, _run_sync)

        for chunk in events:
            phase = chunk.get("current_phase", "")
            error = chunk.get("error", "")
            if error:
                yield f"event: error\ndata: {json.dumps({'phase': phase, 'message': error}, ensure_ascii=False)}\n\n"
                return
            payload = {"phase": phase, "message": _phase_message(phase)}
            yield f"event: step\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

        final = events[-1].get("final_itinerary", {})
        yield f"event: complete\ndata: {json.dumps(final, ensure_ascii=False)}\n\n"


def _phase_message(phase: str) -> str:
    """Map internal phase name to a human-readable progress message."""
    messages = {
        "parse_input": "正在解析您的旅行需求...",
        "fetch_weather": "正在查询目的地天气...",
        "search_poi": "正在搜索热门景点...",
        "search_food": "正在搜索本地美食...",
        "plan_itinerary": "正在为您生成行程...",
        "budget_check": "正在核算预算...",
        "adapt_weather": "正在根据天气调整行程...",
        "add_couple_touch": "正在添加浪漫寄语...",
        "output_format": "正在整理最终行程...",
    }
    return messages.get(phase, f"处理中: {phase}")


@app.post("/api/plan")
async def create_plan(request: TripPlanRequest):
    """Receive trip parameters, run the agent graph, and stream progress via SSE.

    The client should connect with:
        Accept: text/event-stream

    Events fired:
        step     — per-node progress notification
        complete — final TripPlanResponse JSON
        error    — terminal error message
    """
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
        "retry_count": 0,
    }

    return StreamingResponse(
        _stream_graph(initial_state),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
