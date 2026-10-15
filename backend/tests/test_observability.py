"""Tests for P3.2 observability: /metrics endpoint + degraded flag."""

import pytest
from fastapi.testclient import TestClient

from main import app


class TestMetricsEndpoint:
    """/metrics should be exposed and return Prometheus-format text."""

    def test_metrics_returns_200(self):
        client = TestClient(app)
        response = client.get("/metrics")
        assert response.status_code == 200
        # Prometheus exposition is text/plain, not JSON
        assert "text/plain" in response.headers.get("content-type", "")

    def test_metrics_contains_http_duration(self):
        client = TestClient(app)
        # Hit an endpoint first so there's request data
        client.get("/health")
        response = client.get("/metrics")
        assert response.status_code == 200
        body = response.text
        # prometheus-fastapi-instrumentator exposes http_request_duration metrics
        assert "http_request_duration" in body or "http_requests" in body


class TestDegradedFlag:
    """SSE complete payload should carry a `degraded` boolean."""

    @pytest.mark.asyncio
    async def test_complete_payload_has_degraded(self):
        from main import _stream_graph
        from services.storage import generate_plan_id

        state = {
            "user_input": {
                "origin": "Beijing",
                "destination": "Dali",
                "start_date": "2026-09-01",
                "end_date": "2026-09-01",
                "budget": 5000,
                "preferences": ["romantic", "food"],
                "pace": "relaxed",
            },
            "current_phase": "start",
            "error": "",
            "warnings": [],
        }
        chunks = []
        async for chunk in _stream_graph(state, generate_plan_id()):
            chunks.append(chunk)

        # Find the complete event
        for chunk in chunks:
            if "event: complete" in chunk:
                # Extract the JSON data
                for line in chunk.split("\n"):
                    if line.startswith("data:"):
                        import json
                        payload = json.loads(line[5:].strip())
                        assert "degraded" in payload
                        assert isinstance(payload["degraded"], bool)
                        return
        pytest.fail("No complete event found in stream output")
