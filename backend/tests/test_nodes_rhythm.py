"""Tests for the M5 rhythm_control node."""

import copy
import pytest

from agents.state import AgentState
from agents.nodes.rhythm_control import (
    rhythm_control,
    _cap_period,
    _ensure_rest,
    _normalise_day,
    _REST_TEMPLATES_BY_PERIOD,
    _MAX_PER_PERIOD,
)
from agents.nodes.plan_itinerary import _mock_itinerary
from agents.nodes.parse_input import parse_input
from agents.nodes.fetch_weather import fetch_weather
from agents.nodes.search_poi import search_poi
from agents.nodes.search_food import search_food


async def _full_input_state(destination="Dali", budget=5000, days=3):
    user = {
        "origin": "Beijing",
        "destination": destination,
        "start_date": "2026-09-01",
        "end_date": f"2026-09-{days:02d}",
        "budget": budget,
        "preferences": ["romantic", "food"],
        "pace": "relaxed",
    }
    state: AgentState = {
        "user_input": user,
        "current_phase": "start",
        "error": "",
        "warnings": [],
    }
    state.update(await parse_input(state))
    state.update(await fetch_weather(state))
    state.update(await search_poi(state))
    state.update(await search_food(state))
    return state


class TestCapPeriod:
    def test_under_limit_unchanged(self):
        acts = [
            {"name": "A", "type": "景点", "estimated_cost": 100},
            {"name": "B", "type": "美食", "estimated_cost": 60},
        ]
        kept, dropped = _cap_period(acts)
        assert len(kept) == 2
        assert dropped == []

    def test_over_limit_caps_to_two(self):
        acts = [
            {"name": "A", "type": "景点", "estimated_cost": 100},
            {"name": "B", "type": "美食", "estimated_cost": 60},
            {"name": "C", "type": "景点", "estimated_cost": 50},
            {"name": "D", "type": "留白", "estimated_cost": 0},
        ]
        kept, dropped = _cap_period(acts)
        assert len(kept) == _MAX_PER_PERIOD
        assert len(dropped) == 2
        kept_names = {a["name"] for a in kept}
        assert "A" in kept_names
        assert "B" in kept_names
        assert "D" in dropped

    def test_preserves_order_after_cap(self):
        acts = [
            {"name": "first", "type": "景点", "estimated_cost": 200},
            {"name": "second", "type": "美食", "estimated_cost": 80},
            {"name": "third", "type": "景点", "estimated_cost": 150},
        ]
        kept, _ = _cap_period(acts)
        assert [a["name"] for a in kept] == ["first", "third"]


class TestEnsureRest:
    def test_existing_rest_unchanged(self):
        acts = [
            {"name": "A", "type": "景点"},
            {"name": "发呆", "type": "留白"},
        ]
        result = _ensure_rest(acts, "下午", 0, [])
        assert result == acts

    def test_injects_rest_when_missing(self):
        acts = [{"name": "A", "type": "景点"}]
        adjustments = []
        result = _ensure_rest(acts, "下午", 0, adjustments)
        assert len(result) == 2
        assert result[-1]["type"] == "留白"
        assert result[-1]["period"] == "下午"
        assert len(adjustments) == 1
        assert adjustments[0]["kind"] == "inject_rest"

    def test_empty_period_no_injection(self):
        result = _ensure_rest([], "上午", 0, [])
        assert result == []

    def test_period_specific_template(self):
        acts = [{"name": "A", "type": "景点"}]
        result = _ensure_rest(acts, "晚间", 0, [])
        template = _REST_TEMPLATES_BY_PERIOD["晚间"][0]
        assert result[-1]["name"] == template["name"]
        assert result[-1]["start_time"] == template["start_time"]


class TestNormaliseDay:
    def test_caps_overdense_periods(self):
        day = {
            "day_index": 0,
            "activities": [
                {"name": "A", "period": "上午", "type": "景点", "estimated_cost": 100},
                {"name": "B", "period": "上午", "type": "美食", "estimated_cost": 60},
                {"name": "C", "period": "上午", "type": "景点", "estimated_cost": 50},
                {"name": "D", "period": "下午", "type": "景点", "estimated_cost": 80},
            ],
        }
        out, adjustments = _normalise_day(day)
        morning = [a for a in out["activities"] if a["period"] == "上午"]
        assert len(morning) <= _MAX_PER_PERIOD
        assert any(adj["kind"] == "cap" for adj in adjustments)

    def test_injects_rest_for_sparse_period_without_rest(self):
        day = {
            "day_index": 0,
            "activities": [
                {"name": "A", "period": "上午", "type": "景点", "estimated_cost": 100},
            ],
        }
        out, adjustments = _normalise_day(day)
        morning = [a for a in out["activities"] if a["period"] == "上午"]
        assert any(a["type"] == "留白" for a in morning)
        assert any(adj["kind"] == "inject_rest" for adj in adjustments)


class TestRhythmControlNode:
    @pytest.mark.asyncio
    async def test_returns_correct_phase(self):
        state = await _full_input_state()
        result = await rhythm_control({"draft_itinerary": _mock_itinerary(state)})
        assert result["current_phase"] == "rhythm_control"
        assert "draft_itinerary" in result
        assert "rhythm_adjustments" in result

    @pytest.mark.asyncio
    async def test_no_more_than_two_per_period_after_control(self):
        state = await _full_input_state()
        draft = _mock_itinerary(state)
        draft["days"][0]["activities"].append({
            "period": "上午",
            "name": "额外景点",
            "type": "景点",
            "estimated_cost": 90,
            "start_time": "10:00",
            "duration_min": 60,
            "description": "test",
        })
        result = await rhythm_control({"draft_itinerary": draft})
        for day in result["draft_itinerary"]["days"]:
            by_period = {}
            for act in day["activities"]:
                by_period.setdefault(act["period"], 0)
                by_period[act["period"]] += 1
            for period, count in by_period.items():
                assert count <= _MAX_PER_PERIOD, f"period {period} has {count} activities"

    @pytest.mark.asyncio
    async def test_mock_itinerary_already_compliant(self):
        """The M2 mock itinerary should already respect the rhythm."""
        state = await _full_input_state()
        draft = _mock_itinerary(state)
        result = await rhythm_control({"draft_itinerary": copy.deepcopy(draft)})
        cap_adjustments = [a for a in result["rhythm_adjustments"] if a.get("kind") == "cap"]
        assert cap_adjustments == []

    @pytest.mark.asyncio
    async def test_empty_draft_handled(self):
        result = await rhythm_control({"draft_itinerary": {}})
        assert result["draft_itinerary"] == {}
        assert result["rhythm_adjustments"] == []

    @pytest.mark.asyncio
    async def test_does_not_mutate_input(self):
        state = await _full_input_state()
        draft = _mock_itinerary(state)
        original = copy.deepcopy(draft)
        await rhythm_control({"draft_itinerary": draft})
        assert draft == original
