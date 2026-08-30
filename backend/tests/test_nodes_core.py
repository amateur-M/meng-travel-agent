"""Tests for core logic nodes: plan_itinerary, budget_check, adapt_weather."""

import pytest

from agents.state import AgentState
from agents.nodes.parse_input import parse_input
from agents.nodes.fetch_weather import fetch_weather
from agents.nodes.search_poi import search_poi
from agents.nodes.search_food import search_food
from agents.nodes.plan_itinerary import plan_itinerary, _mock_itinerary
from agents.nodes.budget_check import (
    budget_check,
    _daily_costs,
    _rule_based_budget_downgrade,
    _sum_costs,
    _warning_level,
)
from agents.nodes.adapt_weather import (
    adapt_weather,
    _find_indoor_replacement,
    _is_hot,
    _is_rain,
)


def _full_input_state(destination="Dali", budget=5000, days=3, preferences=None):
    """Build a state that has already gone through parse_input + fetchers."""
    user = {
        "origin": "Beijing",
        "destination": destination,
        "start_date": "2026-09-01",
        "end_date": f"2026-09-{days:02d}",
        "budget": budget,
        "preferences": preferences or ["romantic", "food"],
        "pace": "relaxed",
    }
    state: AgentState = {"user_input": user, "current_phase": "start", "error": "", "retry_count": 0}
    state.update(parse_input(state))
    state.update(fetch_weather(state))
    state.update(search_poi(state))
    state.update(search_food(state))
    return state


class TestPlanItinerary:

    def test_mock_itinerary_has_correct_day_count(self):
        state = _full_input_state()
        draft = _mock_itinerary(state)
        assert len(draft["days"]) == 3

    def test_mock_itinerary_each_day_has_activities(self):
        state = _full_input_state()
        draft = _mock_itinerary(state)
        for day in draft["days"]:
            assert len(day["activities"]) >= 3

    def test_mock_itinerary_activities_have_required_keys(self):
        state = _full_input_state()
        draft = _mock_itinerary(state)
        first = draft["days"][0]["activities"][0]
        for key in ["period", "name", "type", "start_time", "duration_min", "estimated_cost", "description"]:
            assert key in first, f"Missing key: {key}"

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

    def test_plan_itinerary_has_rest_activities(self):
        state = _full_input_state()
        result = plan_itinerary(state)
        types = set()
        for day in result["draft_itinerary"]["days"]:
            for act in day["activities"]:
                types.add(act["type"])
        assert len(types) >= 2


class TestBudgetCheck:

    def test_under_budget_passes(self):
        state = _full_input_state(budget=500000)
        state.update(plan_itinerary(state))
        result = budget_check(state)
        assert result["budget_breakdown"]["over_budget"] is False
        assert result["retry_count"] == 0

    def test_over_budget_triggers_downgrade(self):
        state = _full_input_state(budget=1)
        state.update(plan_itinerary(state))
        result = budget_check(state)
        assert result["budget_breakdown"]["downgrade_applied"] is True
        assert result["budget_breakdown"]["over_budget"] is False
        assert result["retry_count"] >= 1

    def test_budget_breakdown_structure(self):
        state = _full_input_state(budget=5000)
        state.update(plan_itinerary(state))
        result = budget_check(state)
        bb = result["budget_breakdown"]
        for key in ["total_budget", "total_spent", "over_budget", "by_day"]:
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

    def test_warning_level_thresholds(self):
        assert _warning_level(4400, 5000) == "ok"
        assert _warning_level(4500, 5000) == "warning"
        assert _warning_level(5001, 5000) == "over"

    def test_over_budget_applies_downgrade(self):
        state = _full_input_state(budget=1)
        state.update(plan_itinerary(state))
        result = budget_check(state)
        breakdown = result["budget_breakdown"]
        assert breakdown["downgrade_applied"] is True
        assert breakdown["total_spent"] <= breakdown["total_budget"]
        assert "days" in result["draft_itinerary"]

    def test_rule_based_downgrade_returns_adjusted_draft(self):
        state = _full_input_state(budget=1)
        state.update(plan_itinerary(state))
        adjusted, adjustments = _rule_based_budget_downgrade(
            state,
            state["draft_itinerary"],
            1,
        )
        assert _sum_costs(adjusted) <= 1
        assert adjustments


class TestAdaptWeather:

    def test_clear_weather_no_changes(self):
        state = _full_input_state()
        state["weather_data"] = {
            "2026-09-01": {"condition": "Sunny", "high": 26, "low": 16, "precip_prob": 0.0},
            "2026-09-02": {"condition": "Sunny", "high": 27, "low": 17, "precip_prob": 0.0},
        }
        state.update(plan_itinerary(state))
        result = adapt_weather(state)
        assert result["current_phase"] == "adapt_weather"
        assert "draft_itinerary" in result

    def test_rainy_weather_returns_result(self):
        state = _full_input_state()
        state["weather_data"] = {
            "2026-09-01": {"condition": "Rain", "high": 24, "low": 15, "precip_prob": 0.8},
            "2026-09-02": {"condition": "Rain", "high": 25, "low": 16, "precip_prob": 0.7},
        }
        state.update(plan_itinerary(state))
        result = adapt_weather(state)
        assert result["current_phase"] == "adapt_weather"

    def test_hot_weather_handled(self):
        state = _full_input_state()
        state["weather_data"] = {
            "2026-09-01": {"condition": "Sunny", "high": 38, "low": 28, "precip_prob": 0.0},
        }
        state.update(plan_itinerary(state))
        result = adapt_weather(state)
        assert result["current_phase"] == "adapt_weather"

    def test_rain_swaps_outdoor_to_indoor(self):
        state = _full_input_state(days=1)
        state["weather_data"] = {
            "2026-09-01": {"condition": "中雨", "high": 24, "low": 18, "precip_prob": 0.8},
        }
        state.update(plan_itinerary(state))
        result = adapt_weather(state)
        swaps = result["weather_swaps"]
        assert any(item["adjustment_type"] == "swap" for item in swaps)
        assert any(
            activity.get("indoor_backup")
            for day in result["draft_itinerary"]["days"]
            for activity in day["activities"]
        )

    def test_hot_weather_moves_outdoor_activity(self):
        state = _full_input_state(days=1)
        state["weather_data"] = {
            "2026-09-01": {"condition": "晴", "high": 38, "low": 28, "precip_prob": 0.0},
        }
        state.update(plan_itinerary(state))
        result = adapt_weather(state)
        activities = [
            activity
            for day in result["draft_itinerary"]["days"]
            for activity in day["activities"]
        ]
        assert any(
            activity.get("start_time") in ("08:00", "17:00")
            and activity.get("weather_note")
            for activity in activities
        )

    def test_weather_condition_helpers(self):
        assert _is_rain({"condition": "Rain", "condition_en": "rain"})
        assert _is_rain({"condition": "雷阵雨"})
        assert _is_hot({"high": 36})
        assert not _is_hot({"high": 35})

    def test_find_indoor_replacement_returns_dict(self):
        pois = [
            {"name": "Museum", "type": "culture", "rating": 4.2, "indoor": True},
            {"name": "Lake", "type": "nature", "rating": 4.8, "indoor": False},
        ]
        indoor_map = {p["name"]: p for p in pois if p.get("indoor")}
        result = _find_indoor_replacement({"name": "Lake", "type": "nature"}, indoor_map, pois)
        assert result is not None
        assert result.get("indoor") is True

    def test_find_indoor_replacement_fallback(self):
        result = _find_indoor_replacement({"name": "Unknown", "type": "nature"}, {}, [])
        assert result is not None
