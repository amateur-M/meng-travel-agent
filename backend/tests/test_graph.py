"""Integration tests for the full LangGraph travel-planning pipeline."""

import pytest

from agents.state import AgentState
from agents.graph import graph, build_graph, _route_after_budget


class TestRouteAfterBudget:
    """Conditional edge routing logic."""

    def test_under_budget_routes_to_adapt_weather(self):
        state: AgentState = {
            "budget_breakdown": {"over_budget": False},
            "retry_count": 0,
        }
        assert _route_after_budget(state) == "adapt_weather"

    def test_over_budget_under_retry_limit_routes_to_plan_itinerary(self):
        state: AgentState = {
            "budget_breakdown": {"over_budget": True},
            "retry_count": 0,
        }
        assert _route_after_budget(state) == "plan_itinerary"

    def test_over_budget_first_retry_loops(self):
        state: AgentState = {
            "budget_breakdown": {"over_budget": True},
            "retry_count": 1,
        }
        assert _route_after_budget(state) == "plan_itinerary"

    def test_over_budget_max_retries_routes_to_adapt_weather(self):
        state: AgentState = {
            "budget_breakdown": {"over_budget": True},
            "retry_count": 2,
        }
        assert _route_after_budget(state) == "adapt_weather"

    def test_missing_budget_breakdown_defaults_to_pass(self):
        state: AgentState = {"retry_count": 0}
        assert _route_after_budget(state) == "adapt_weather"


class TestGraphBuild:
    """Verify the graph compiles without error."""

    def test_build_graph_returns_compiled_graph(self):
        g = build_graph()
        assert g is not None

    def test_module_level_graph_is_compiled(self):
        assert graph is not None


class TestGraphInvoke:
    """End-to-end graph execution with mock data (no API keys)."""

    def _initial_state(self, destination="Dali", budget=5000, days=2, pace="relaxed"):
        return {
            "user_input": {
                "origin": "Beijing",
                "destination": destination,
                "start_date": "2026-09-01",
                "end_date": f"2026-09-0{days+1}",
                "budget": budget,
                "preferences": ["romantic", "food"],
                "pace": pace,
            },
            "current_phase": "start",
            "error": "",
            "retry_count": 0,
        }

    def test_full_graph_completes_dali(self):
        """Smoke test: graph completes end-to-end for Dali."""
        state = self._initial_state()
        result = graph.invoke(state)
        final = result.get("final_itinerary", {})
        assert "plan_id" in final
        assert final["status"] == "completed"
        assert len(final["days"]) == 2

    def test_full_graph_completes_lijiang(self):
        """Smoke test: graph completes for Lijiang."""
        state = self._initial_state(destination="Lijiang", budget=6000, days=3)
        result = graph.invoke(state)
        final = result.get("final_itinerary", {})
        assert len(final["days"]) == 3

    def test_full_graph_completes_sanya(self):
        """Smoke test: graph completes for Sanya."""
        state = self._initial_state(destination="Sanya", budget=8000, days=2)
        result = graph.invoke(state)
        final = result.get("final_itinerary", {})
        assert final["status"] == "completed"

    def test_single_day_trip(self):
        """Graph handles 1-day trips."""
        state = self._initial_state(destination="Dali", budget=3000, days=1)
        result = graph.invoke(state)
        final = result.get("final_itinerary", {})
        assert len(final["days"]) == 1

    def test_budget_breakdown_present(self):
        state = self._initial_state()
        result = graph.invoke(state)
        bb = result.get("budget_breakdown", {})
        assert "total_budget" in bb
        assert "total_spent" in bb
        assert "over_budget" in bb

    def test_couple_notes_present(self):
        state = self._initial_state()
        result = graph.invoke(state)
        notes = result.get("couple_notes", [])
        assert len(notes) > 0

    def test_every_activity_has_couple_note(self):
        state = self._initial_state()
        result = graph.invoke(state)
        for day in result.get("final_itinerary", {}).get("days", []):
            for act in day.get("activities", []):
                assert "couple_note" in act, f"Activity missing couple_note"
                assert act["couple_note"] != ""

    def test_unknown_destination_still_completes(self):
        """Graph should complete even for unmapped destinations."""
        state = self._initial_state(destination="NowhereVille")
        result = graph.invoke(state)
        final = result.get("final_itinerary", {})
        assert final["status"] == "completed"

    def test_packed_pace(self):
        state = self._initial_state(pace="packed", days=1)
        result = graph.invoke(state)
        final = result.get("final_itinerary", {})
        assert len(final["days"]) == 1

    def test_graph_stream_mode(self):
        """Verify stream mode yields chunks."""
        state = self._initial_state(days=1)
        chunks = list(graph.stream(state, stream_mode="values"))
        assert len(chunks) > 0
        last = chunks[-1]
        assert "final_itinerary" in last or "current_phase" in last
