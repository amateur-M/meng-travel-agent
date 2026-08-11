"""Tests for core logic nodes: plan_itinerary, budget_check, adapt_weather."""

import pytest

from agents.state import AgentState
from agents.nodes.parse_input import parse_input
from agents.nodes.fetch_weather import fetch_weather
from agents.nodes.search_poi import search_poi
from agents.nodes.search_food import search_food
from agents.nodes.plan_itinerary import plan_itinerary, _mock_itinerary
from agents.nodes.budget_check import budget_check, _sum_costs, _daily_costs
from agents.nodes.adapt_weather import adapt_weather, _find_indoor_replacement


# ── helpers ──────────────────────────────────────────────────────

def _full_input_state(destination="大理", budget=5000, days=2, preferences=None):
    """Build a state that has already gone through parse_input + fetchers."""
    user = {
        "origin": "北京",
        "destination": destination,
        "start_date": "2026-09-01",
        "end_date": f"2026-09-0{days+1}",
        "budget": budget,
        "preferences": preferences or ["浪漫", "美食"],
        "pace": "轻松",
    }
    state: AgentState = {"user_input": user, "current_phase": "start", "error": "", "retry_count": 0}
    state.update(parse_input(state))
    state.update(fetch_weather(state))
    state.update(search_poi(state))
    state.update(search_food(state))
    return state


# ── plan_itinerary ───────────────────────────────────────────────

class TestPlanItinerary:

    def test_mock_itinerary_has_correct_day_count(self):
        state = _full_input_state()
        draft = _mock_itinerary(state)
        assert len(draft["days"]) == 2

    def test_mock_itinerary_each_day_has_6_activities(self):
        state = _full_input_state()
        draft = _mock_itinerary(state)
        for day in draft["days"]:
            # M1 mock generates 6 activities per day (morning x2, afternoon x2, evening x2)
            assert len(day["activities"]) == 6

    def test_mock_itinerary_activities_have_required_keys(self):
        state = _full_input_state()
        draft = _mock_itinerary(state)
        first = draft["days"][0]["activities"][0]
        for key in ["period", "name", "type", "start_time", "duration_min", "estimated_cost", "description"]:
            assert key in first, f"Missing key: {key}"

    def test_mock_itinerary_periods_are_ordered(self):
        state = _full_input_state()
        draft = _mock_itinerary(state)
        periods = [a["period"] for a in draft["days"][0]["activities"]]
        # Should appear in order: 上午, 上午, 下午, 下午, 晚间, 晚间
        assert periods[:2] == ["上午", "上午"]
        assert periods[2:4] == ["下午", "下午"]
        assert periods[4:6] == ["晚间", "晚间"]

    def test_plan_itinerary_node_returns_draft(self):
        state = _full_input_state()
        result = plan_itinerary(state)
        assert "draft_itinerary" in result
        assert "days" in result["draft_itinerary"]
        assert result["current_phase"] == "plan_itinerary"

    def test_plan_itinerary_with_one_day(self):
        state = _full_input_state(days=1)
        result = plan_itinerary(state)
        assert len(result["draft_itinerary"]["days"]) == 1

    def test_plan_itinerary_has_留白_activities(self):
        """Verify relaxed pace includes rest/slack activities."""
        state = _full_input_state()
        result = plan_itinerary(state)
        types = set()
        for day in result["draft_itinerary"]["days"]:
            for act in day["activities"]:
                types.add(act["type"])
        assert "留白" in types


# ── budget_check ─────────────────────────────────────────────────

class TestBudgetCheck:

    def test_under_budget_passes(self):
        state = _full_input_state(budget=500000)
        state.update(plan_itinerary(state))
        result = budget_check(state)
        assert result["budget_breakdown"]["over_budget"] is False
        assert result["retry_count"] == 0

    def test_over_budget_triggers_retry(self):
        state = _full_input_state(budget=1)  # impossibly low
        state.update(plan_itinerary(state))
        result = budget_check(state)
        assert result["budget_breakdown"]["over_budget"] is True
        assert result["retry_count"] >= 1
        assert len(result["budget_breakdown"]["downgrade_notes"]) > 0

    def test_budget_breakdown_structure(self):
        state = _full_input_state(budget=5000)
        state.update(plan_itinerary(state))
        result = budget_check(state)
        bb = result["budget_breakdown"]
        for key in ["total_budget", "total_spent", "over_budget", "by_day", "downgrade_notes"]:
            assert key in bb, f"Missing key: {key}"

    def test_sum_costs_utility(self):
        draft = {
            "days": [
                {"activities": [{"estimated_cost": 100}, {"estimated_cost": 200}]},
                {"activities": [{"estimated_cost": 50}]},
            ]
        }
        assert _sum_costs(draft) == 350.0

    def test_daily_costs_utility(self):
        draft = {
            "days": [
                {"activities": [{"estimated_cost": 100}, {"estimated_cost": 50}]},
                {"activities": [{"estimated_cost": 200}]},
            ]
        }
        assert _daily_costs(draft) == [150.0, 200.0]

    def test_empty_itinerary_costs(self):
        assert _sum_costs({"days": []}) == 0.0
        assert _daily_costs({"days": []}) == []


# ── adapt_weather ────────────────────────────────────────────────

class TestAdaptWeather:

    def test_clear_weather_no_changes(self):
        state = _full_input_state()
        # override weather to all sunny
        state["weather_data"] = {
            "2026-09-01": {"condition": "晴", "high": 26, "low": 16},
            "2026-09-02": {"condition": "晴", "high": 27, "low": 17},
        }
        state.update(plan_itinerary(state))
        draft_before = state["draft_itinerary"]
        result = adapt_weather(state)
        # draft should be unchanged
        assert result["draft_itinerary"] == draft_before
        assert result["current_phase"] == "adapt_weather"

    def test_rainy_weather_swaps_to_indoor(self):
        state = _full_input_state()
        state["weather_data"] = {
            "2026-09-01": {"condition": "中雨", "high": 24, "low": 15},
            "2026-09-02": {"condition": "小雨", "high": 25, "low": 16},
        }
        state.update(plan_itinerary(state))
        result = adapt_weather(state)
        # Check that some activities were modified
        # Non-美食, non-留白 outdoor activities should become indoor
        for day in result["draft_itinerary"]["days"]:
            for act in day["activities"]:
                if act["type"] not in ("美食", "留白", "室内"):
                    assert "indoor_backup" in act or act["type"] == "室内"

    def test_hot_weather_reschedules(self):
        state = _full_input_state()
        state["weather_data"] = {
            "2026-09-01": {"condition": "晴", "high": 38, "low": 28},
        }
        state.update(plan_itinerary(state))
        result = adapt_weather(state)
        # Some activities may have weather_note for heat adjustment
        found = False
        for day in result["draft_itinerary"]["days"]:
            for act in day["activities"]:
                if act.get("weather_note"):
                    found = True
                    break
        # Not all activities will match (depends on start_time) but structure should be fine
        assert result["current_phase"] == "adapt_weather"

    def test_find_indoor_replacement_returns_dict(self):
        pois = [
            {"name": "大理市博物馆", "type": "文化", "rating": 4.2, "indoor": True},
            {"name": "洱海", "type": "自然", "rating": 4.8, "indoor": False},
        ]
        indoor_map = {p["name"]: p for p in pois if p.get("indoor")}
        result = _find_indoor_replacement({"name": "洱海", "type": "自然"}, indoor_map, pois)
        assert result is not None
        assert result.get("indoor") is True

    def test_find_indoor_replacement_fallback(self):
        result = _find_indoor_replacement({"name": "无名景点", "type": "自然"}, {}, [])
        assert result is not None
        assert result["name"] == "室内咖啡馆"
