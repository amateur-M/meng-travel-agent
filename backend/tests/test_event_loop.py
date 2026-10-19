"""The event loop must never be blocked by storage I/O (V2 P0.2 / V3).

Both stores use synchronous drivers (psycopg's sync pool — see
``services/conversation_store`` for why the async driver is unusable on
Windows), so every call must be handed to a worker thread. When one is missed,
a slow or unreachable database stalls *every* concurrent request: with
PostgreSQL down the pool timeout is 5 seconds and the whole server goes quiet.

These tests measure **event-loop lag** while a storage call is deliberately
slow. Lag is the right metric: wall-clock timing of two requests cannot detect
the problem, because a frozen loop also freezes the clock-reading coroutine
that would have reported it.
"""

import asyncio
import time
from contextlib import suppress
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import app

PLAN_BODY = {
    "origin": "北京",
    "destination": "大理",
    "start_date": "2026-09-01",
    "end_date": "2026-09-03",
    "budget": 5000,
    "preferences": ["浪漫", "美食"],
    "pace": "轻松",
}

HEALTHY = {"configured": True, "connected": True, "error": None}

SLOW_SECONDS = 0.4
# A correctly offloaded call keeps lag in the low milliseconds; the blocking
# version pins it to ~SLOW_SECONDS. The threshold sits far from both.
MAX_LAG_SECONDS = 0.15


def _instant_health():
    """Keep /health cheap: it is the probe, not the subject."""
    return (
        patch("services.storage.plan_store.health", return_value=dict(HEALTHY)),
        patch("services.conversation_store.conversation_store.health", new=AsyncMock(return_value=dict(HEALTHY))),
    )


@pytest.fixture
def instant_health():
    plan_health, chat_health = _instant_health()
    with plan_health, chat_health:
        yield


async def _measure_loop_lag(work):
    """Run *work* while sampling how late a 10ms timer fires."""
    loop = asyncio.get_running_loop()
    lag = 0.0

    async def sampler():
        nonlocal lag
        while True:
            started = loop.time()
            await asyncio.sleep(0.01)
            lag = max(lag, loop.time() - started - 0.01)

    watcher = asyncio.create_task(sampler())
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await work(client)
    finally:
        watcher.cancel()
        with suppress(asyncio.CancelledError):
            await watcher
    return lag


@pytest.mark.asyncio
async def test_slow_plan_save_does_not_stall_the_loop(instant_health):
    """POST /api/plan writes to the plan store before returning."""

    def slow_save(*args, **kwargs):
        time.sleep(SLOW_SECONDS)
        return True

    with patch("services.storage.plan_store.save", side_effect=slow_save), patch(
        "api.plan._run_graph_to_queue", new=AsyncMock()
    ):
        lag = await _measure_loop_lag(
            lambda client: client.post("/api/plan", json=PLAN_BODY)
        )

    assert lag < MAX_LAG_SECONDS, (
        f"event loop stalled {lag:.3f}s during a {SLOW_SECONDS}s plan write — "
        "plan_store.save is being called on the loop instead of via asyncio.to_thread"
    )


@pytest.mark.asyncio
async def test_slow_plan_read_does_not_stall_the_loop(instant_health):
    """GET /api/plan/{id} reads from the same sync pool."""

    def slow_get(*args, **kwargs):
        time.sleep(SLOW_SECONDS)
        return None

    with patch("services.storage.plan_store.get", side_effect=slow_get):
        lag = await _measure_loop_lag(lambda client: client.get("/api/plan/whatever"))

    assert lag < MAX_LAG_SECONDS, (
        f"event loop stalled {lag:.3f}s during a {SLOW_SECONDS}s plan read — "
        "plan_store.get is being called on the loop instead of via asyncio.to_thread"
    )


@pytest.mark.asyncio
async def test_slow_plan_list_does_not_stall_the_loop(instant_health):
    """GET /api/plan/history is hit by the sidebar on every page load."""

    def slow_list(*args, **kwargs):
        time.sleep(SLOW_SECONDS)
        return []

    with patch("services.storage.plan_store.list", side_effect=slow_list):
        lag = await _measure_loop_lag(lambda client: client.get("/api/plan/history"))

    assert lag < MAX_LAG_SECONDS, (
        f"event loop stalled {lag:.3f}s during a {SLOW_SECONDS}s history read — "
        "plan_store.list is being called on the loop instead of via asyncio.to_thread"
    )


@pytest.mark.asyncio
async def test_slow_feedback_write_does_not_stall_the_loop(instant_health):
    """POST /api/plan/{id}/feedback is on the hot path after a plan renders."""

    def slow_feedback(*args, **kwargs):
        time.sleep(SLOW_SECONDS)
        return True

    with patch("services.storage.plan_store.save_feedback", side_effect=slow_feedback):
        lag = await _measure_loop_lag(
            lambda client: client.post(
                "/api/plan/p1/feedback?activity_name=洱海骑行&thumbs=up"
            )
        )

    assert lag < MAX_LAG_SECONDS, (
        f"event loop stalled {lag:.3f}s during a {SLOW_SECONDS}s feedback write — "
        "plan_store.save_feedback is being called on the loop instead of via asyncio.to_thread"
    )
