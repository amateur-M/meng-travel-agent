"""Plan execution pipeline (V4/P1: extracted from main.py).

Owns the single execution of the LangGraph pipeline for a ``plan_id`` and the
in-memory bus that feeds SSE frames to reconnecting clients.

Deduplication note (T1.3): ``main.py`` used to carry two near-identical copies
of this logic — ``_stream_graph`` (a generator, kept only for tests) and
``_run_graph_to_queue`` (the production background task). They differed only in
*where* the frames went. Here ``_stream_graph`` is the single source of truth
and ``_run_graph_to_queue`` is a thin adapter that pumps it into a queue, so the
graph-running/store-writing/error-handling body exists exactly once.
"""

import asyncio
import logging
from typing import AsyncGenerator

from agents.graph import graph
from schemas import TripPlanResponse
from services.storage import plan_store
from services.sse import _sse, _emit_node_events

logger = logging.getLogger("coupletrip")


# ── Plan stream bus (P0.3) ──────────────────────────────────────
# In-memory event queues keyed by plan_id. The background graph task
# puts SSE frames into the queue; GET /api/plan/{plan_id}/stream
# consumes them. When the graph completes, a sentinel None is pushed
# to signal end-of-stream.
#
# Known limitation: this is process memory, so "reconnect to the same stream"
# only works within one worker. Multi-worker deployment needs a real broker —
# see memory/UPGRADE_V3_CONVERSATION_MEMORY.md §6.1 for the trigger conditions.

plan_streams: dict[str, asyncio.Queue] = {}
_STREAM_SENTINEL = None  # pushed to queue when stream is done


async def _stream_graph(initial_state: dict, plan_id: str) -> AsyncGenerator[str, None]:
    """Run the LangGraph pipeline once and yield SSE events per node.

    This is the canonical pipeline body: it streams each node's events, writes
    the final result (or the error) back to ``plan_store`` via a worker thread
    so the event loop is never blocked, and always terminates with a
    ``complete`` or ``error`` frame.
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
                        await asyncio.to_thread(
                            plan_store.update, plan_id, {"error": error}, status="error"
                        )
                        return
                    for event in _emit_node_events(phase, update):
                        yield event
                        await asyncio.sleep(0)

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

        await asyncio.to_thread(
            plan_store.update, plan_id, complete_payload, status="completed"
        )
        yield _sse("complete", complete_payload)

    except Exception as exc:
        logger.exception("Unhandled error in graph pipeline")
        await asyncio.to_thread(
            plan_store.update, plan_id, {"error": str(exc)}, status="error"
        )
        yield _sse("error", {"phase": "unknown", "message": str(exc)})


async def _run_graph_to_queue(initial_state: dict, plan_id: str, queue: asyncio.Queue) -> None:
    """Background task: pump :func:`_stream_graph` into *queue*.

    This is the single execution of the graph — regardless of how many times
    the client connects/reconnects to GET stream, the graph runs exactly once
    per plan_id. The sentinel is always pushed (even on an unexpected error) so
    a waiting consumer never hangs.
    """
    try:
        async for event in _stream_graph(initial_state, plan_id):
            await queue.put(event)
    finally:
        await queue.put(_STREAM_SENTINEL)
