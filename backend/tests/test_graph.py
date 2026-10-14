"""Integration tests for the full LangGraph travel-planning pipeline."""

import pytest

from agents.state import AgentState
from agents.graph import graph, build_graph


# P6: TestRouteAfterBudget removed — _route_after_budget was deleted together
# with the unreachable conditional retry edge in graph.py.


class TestGraphBuild:
    """Verify the graph compiles without error."""

    def test_build_graph_returns_compiled_graph(self):
        g = build_graph()
        assert g is not None

    def test_module_level_graph_is_compiled(self):
        assert graph is not None


class TestGraphInvoke:
    """End-to-end graph execution with mock data (no API keys)."""

    def _initial_state(self, destination="Dali", budget=5000, days=3, pace="relaxed"):
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

    @pytest.mark.asyncio
    async def test_full_graph_completes_dali(self):
        """Smoke test: graph completes end-to-end for Dali."""
        state = self._initial_state()
        result = await graph.ainvoke(state)
        final = result.get("final_itinerary", {})
        assert "plan_id" in final
        assert final["status"] == "completed"
        assert len(final["days"]) == 3

    @pytest.mark.asyncio
    async def test_full_graph_completes_lijiang(self):
        """Smoke test: graph completes for Lijiang."""
        state = self._initial_state(destination="Lijiang", budget=6000, days=3)
        result = await graph.ainvoke(state)
        final = result.get("final_itinerary", {})
        assert len(final["days"]) == 3

    @pytest.mark.asyncio
    async def test_full_graph_completes_sanya(self):
        """Smoke test: graph completes for Sanya."""
        state = self._initial_state(destination="Sanya", budget=8000, days=2)
        result = await graph.ainvoke(state)
        final = result.get("final_itinerary", {})
        assert final["status"] == "completed"

    @pytest.mark.asyncio
    async def test_single_day_trip(self):
        """Graph handles 1-day trips."""
        state = self._initial_state(destination="Dali", budget=3000, days=1)
        result = await graph.ainvoke(state)
        final = result.get("final_itinerary", {})
        assert len(final["days"]) == 1

    @pytest.mark.asyncio
    async def test_budget_breakdown_present(self):
        state = self._initial_state()
        result = await graph.ainvoke(state)
        bb = result.get("budget_breakdown", {})
        assert "total_budget" in bb
        assert "total_spent" in bb
        assert "over_budget" in bb
        assert "warning_level" in bb
        assert "spending_ratio" in bb

    @pytest.mark.asyncio
    async def test_weather_swaps_present_in_final(self):
        state = self._initial_state()
        result = await graph.ainvoke(state)
        final = result.get("final_itinerary", {})
        assert "weather_swaps" in final
        assert isinstance(final["weather_swaps"], list)

    @pytest.mark.asyncio
    async def test_couple_notes_present(self):
        state = self._initial_state()
        result = await graph.ainvoke(state)
        notes = result.get("couple_notes", [])
        assert len(notes) > 0

    @pytest.mark.asyncio
    async def test_every_activity_has_couple_note(self):
        state = self._initial_state()
        result = await graph.ainvoke(state)
        for day in result.get("final_itinerary", {}).get("days", []):
            for act in day.get("activities", []):
                assert "couple_note" in act, f"Activity missing couple_note"
                assert act["couple_note"] != ""

    @pytest.mark.asyncio
    async def test_unknown_destination_still_completes(self):
        """Graph should complete even for unmapped destinations."""
        state = self._initial_state(destination="NowhereVille")
        result = await graph.ainvoke(state)
        final = result.get("final_itinerary", {})
        assert final["status"] == "completed"

    @pytest.mark.asyncio
    async def test_packed_pace(self):
        state = self._initial_state(pace="packed", days=1)
        result = await graph.ainvoke(state)
        final = result.get("final_itinerary", {})
        assert len(final["days"]) == 1

    @pytest.mark.asyncio
    async def test_graph_stream_mode(self):
        """Verify stream mode yields chunks."""
        state = self._initial_state(days=1)
        chunks = []
        async for chunk in graph.astream(state, stream_mode="values"):
            chunks.append(chunk)
        assert len(chunks) > 0
        last = chunks[-1]
        assert "final_itinerary" in last or "current_phase" in last
