"""Tests for T0.4: storage state is visible instead of silently degraded.

The V2 persistence layer used to swallow failures (every PlanStore call
returned None/False/[]) with only a warning log, so a broken local database
was indistinguishable from "nothing saved yet".  These tests pin the new
behaviour: ``/health`` reports the real state and the reason.
"""

import pytest
from fastapi.testclient import TestClient

from main import app, _report_storage_status
from services.session_store import session_store
from services.storage import plan_store


class TestHealthEndpoint:
    """/health stays a liveness probe but exposes storage state."""

    def test_always_returns_200(self):
        """Docker healthcheck and frontend depends_on rely on HTTP 200."""
        client = TestClient(app)
        assert client.get("/health").status_code == 200

    def test_reports_storage_shape(self):
        client = TestClient(app)
        body = client.get("/health").json()

        assert body["service"] == "coupletrip"
        assert body["status"] in ("ok", "degraded")
        for backend in ("postgres", "redis"):
            entry = body["storage"][backend]
            assert set(entry) == {"configured", "connected", "error"}
            assert isinstance(entry["connected"], bool)

    def test_status_reflects_storage_state(self):
        """`status` must be derived from the reported state, never hardcoded ok."""
        client = TestClient(app)
        body = client.get("/health").json()
        connected = (
            body["storage"]["postgres"]["connected"]
            and body["storage"]["redis"]["connected"]
        )
        assert body["status"] == ("ok" if connected else "degraded")

    def test_degraded_reports_the_reason(self, monkeypatch):
        """An unreachable backend must surface *why*, not just fail silently."""
        monkeypatch.setattr("services.storage._pool_unavailable", True)
        monkeypatch.setattr("services.storage._pool_error", "OperationalError: test failure")

        client = TestClient(app)
        body = client.get("/health").json()

        assert body["status"] == "degraded"
        postgres = body["storage"]["postgres"]
        assert postgres["connected"] is False
        assert "test failure" in postgres["error"]


class TestStoreHealth:
    """health() must never raise — it is called from an unauthenticated probe."""

    def test_plan_store_health_shape(self):
        result = plan_store.health()
        assert set(result) == {"configured", "connected", "error"}
        assert isinstance(result["connected"], bool)

    def test_plan_store_health_after_failure(self, monkeypatch):
        monkeypatch.setattr("services.storage._pool_unavailable", True)
        monkeypatch.setattr("services.storage._pool_error", "boom")
        result = plan_store.health()
        assert result["connected"] is False
        assert result["error"] == "boom"

    @pytest.mark.asyncio
    async def test_session_store_health_shape(self):
        result = await session_store.health()
        assert set(result) == {"configured", "connected", "error"}
        assert isinstance(result["connected"], bool)


class TestStartupReport:
    """Startup surfaces the state once, and never blocks app boot."""

    @pytest.mark.asyncio
    async def test_report_storage_status_does_not_raise(self):
        await _report_storage_status()
