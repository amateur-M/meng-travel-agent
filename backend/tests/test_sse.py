"""Tests for the M6 SSE streaming endpoint and event types.

Verifies that _stream_graph emits the full set of SSE events:
  step, partial, budget_alert, weather_swap, message, complete, error
and that stream_mode="updates" works correctly with the LangGraph pipeline.
"""

import json
import asyncio
import pytest

from main import _stream_graph, _emit_node_events, _sse, _phase_message
from agents.state import AgentState


def _initial_state(destination="Dali", budget=5000, days=3, pace="relaxed"):
    return {
        "user_input": {
            "origin": "Beijing",
            "destination": destination,
            "start_date": "2026-09-01",
            "end_date": f"2026-09-{days:02d}",
            "budget": budget,
            "preferences": ["romantic", "food"],
            "pace": pace,
        },
        "current_phase": "start",
        "error": "",
        "warnings": [],
    }


def _parse_sse_events(raw_chunks: list[str]) -> list[tuple[str, dict]]:
    """Parse a list of raw SSE string chunks into (event_name, data_dict) pairs."""
    events = []
    for chunk in raw_chunks:
        # Each chunk may contain multiple events separated by \n\n
        for block in chunk.split("\n\n"):
            if not block.strip():
                continue
            name = ""
            data_lines = []
            for line in block.split("\n"):
                if line.startswith("event:"):
                    name = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].strip())
            if name and data_lines:
                try:
                    data = json.loads("\n".join(data_lines))
                except json.JSONDecodeError:
                    data = {"raw": "\n".join(data_lines)}
                events.append((name, data))
    return events


# ── Unit tests for helpers ──────────────────────────────────────

class TestSSEHelpers:
    def test_sse_format(self):
        result = _sse("step", {"phase": "parse_input", "message": "test"})
        assert "event: step" in result
        assert '"phase": "parse_input"' in result
        assert result.endswith("\n\n")

    def test_phase_message_known(self):
        assert "天气" in _phase_message("fetch_weather")
        assert "景点" in _phase_message("search_poi")

    def test_phase_message_unknown(self):
        assert "处理中" in _phase_message("unknown_phase")

    def test_emit_step_always_present(self):
        events = _emit_node_events("parse_input", {"parsed_params": {}})
        assert len(events) == 1
        assert "event: step" in events[0]

    def test_emit_partial_for_plan_itinerary(self):
        update = {
            "draft_itinerary": {
                "days": [
                    {
                        "day_index": 0,
                        "weather": "晴",
                        "activities": [
                            {"name": "洱海骑行", "period": "上午"},
                            {"name": "古城漫步", "period": "下午"},
                        ],
                    }
                ]
            },
            "current_phase": "plan_itinerary",
        }
        events = _emit_node_events("plan_itinerary", update)
        # 1 step + 1 partial
        assert len(events) == 2
        assert "event: step" in events[0]
        assert "event: partial" in events[1]
        assert '"day_index": 0' in events[1]

    def test_emit_budget_alert(self):
        update = {
            "budget_breakdown": {
                "total_spent": 5200,
                "total_budget": 5000,
                "warning_level": "over",
                "spending_ratio": 1.04,
                "downgrade_applied": True,
                "downgrade_notes": ["降级说明"],
            },
            "downgrade_suggestions": [{"reason": "test"}],
            "current_phase": "budget_check",
        }
        events = _emit_node_events("budget_check", update)
        assert len(events) == 2  # step + budget_alert
        assert "event: budget_alert" in events[1]
        assert '"warning_level": "over"' in events[1]

    def test_emit_weather_swap(self):
        update = {
            "weather_swaps": [
                {
                    "day_index": 0,
                    "original_name": "洱海骑行",
                    "replacement_name": "室内咖啡馆",
                    "reason": "雨天切换",
                    "adjustment_type": "swap",
                }
            ],
            "current_phase": "adapt_weather",
        }
        events = _emit_node_events("adapt_weather", update)
        assert len(events) == 2  # step + weather_swap
        assert "event: weather_swap" in events[1]

    def test_emit_message_events(self):
        update = {
            "draft_itinerary": {
                "days": [
                    {
                        "day_index": 0,
                        "activities": [
                            {"name": "洱海骑行", "couple_note": "和你一起看洱海"},
                            {"name": "古城漫步", "couple_note": "牵手走过旧时光"},
                        ],
                    }
                ]
            },
            "current_phase": "add_couple_touch",
        }
        events = _emit_node_events("add_couple_touch", update)
        assert len(events) == 3  # step + 2 messages
        assert "event: message" in events[1]
        assert "event: message" in events[2]

    def test_emit_no_budget_alert_when_empty(self):
        update = {
            "budget_breakdown": {},
            "current_phase": "budget_check",
        }
        events = _emit_node_events("budget_check", update)
        assert len(events) == 1  # only step

    def test_emit_no_weather_swap_when_empty(self):
        update = {
            "weather_swaps": [],
            "current_phase": "adapt_weather",
        }
        events = _emit_node_events("adapt_weather", update)
        assert len(events) == 1  # only step


# ── Integration tests for the full stream ───────────────────────

class TestStreamGraphIntegration:
    """Verify _stream_graph produces a complete SSE event sequence."""

    @pytest.mark.asyncio
    async def test_stream_yields_step_events(self):
        state = _initial_state(days=1)
        chunks = []
        async for chunk in _stream_graph(state):
            chunks.append(chunk)
        events = _parse_sse_events(chunks)
        event_names = [name for name, _ in events]

        # Must contain at least one step event
        assert "step" in event_names
        # Must end with complete
        assert event_names[-1] == "complete"

    @pytest.mark.asyncio
    async def test_stream_yields_partial_events(self):
        state = _initial_state(days=1)
        chunks = []
        async for chunk in _stream_graph(state):
            chunks.append(chunk)
        events = _parse_sse_events(chunks)
        event_names = [name for name, _ in events]

        # plan_itinerary should produce at least one partial event
        assert "partial" in event_names

    @pytest.mark.asyncio
    async def test_stream_yields_message_events(self):
        state = _initial_state(days=1)
        chunks = []
        async for chunk in _stream_graph(state):
            chunks.append(chunk)
        events = _parse_sse_events(chunks)
        event_names = [name for name, _ in events]

        # add_couple_touch should produce message events
        assert "message" in event_names
        # Verify message event structure
        message_events = [data for name, data in events if name == "message"]
        assert len(message_events) > 0
        for msg in message_events:
            assert "day" in msg
            assert "activity" in msg
            assert "text" in msg
            assert len(msg["text"]) > 0

    @pytest.mark.asyncio
    async def test_stream_complete_has_valid_response(self):
        state = _initial_state(days=2)
        chunks = []
        async for chunk in _stream_graph(state):
            chunks.append(chunk)
        events = _parse_sse_events(chunks)

        complete_events = [data for name, data in events if name == "complete"]
        assert len(complete_events) == 1
        payload = complete_events[0]
        assert "plan_id" in payload
        assert "days" in payload
        assert len(payload["days"]) == 2
        assert payload["status"] == "completed"

    @pytest.mark.asyncio
    async def test_stream_event_order(self):
        """Steps should precede complete; partials should come before messages."""
        state = _initial_state(days=1)
        chunks = []
        async for chunk in _stream_graph(state):
            chunks.append(chunk)
        events = _parse_sse_events(chunks)
        event_names = [name for name, _ in events]

        complete_idx = event_names.index("complete")
        # All step events must come before complete
        for i, name in enumerate(event_names):
            if name == "step":
                assert i < complete_idx

        # partial events should come before message events
        if "partial" in event_names and "message" in event_names:
            first_partial = event_names.index("partial")
            first_message = event_names.index("message")
            assert first_partial < first_message

    @pytest.mark.asyncio
    async def test_stream_error_on_bad_state(self):
        """An initial state with an error field should propagate gracefully."""
        state = _initial_state(days=1)
        # Inject an error by breaking the graph input
        state["user_input"] = None
        chunks = []
        async for chunk in _stream_graph(state):
            chunks.append(chunk)

        # Should still produce some output (either error or complete)
        assert len(chunks) > 0
