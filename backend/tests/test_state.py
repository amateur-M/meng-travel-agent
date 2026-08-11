"""Tests for AgentState TypedDict and custom reducers."""

import pytest
from agents.state import AgentState, _latest_str


class TestLatestStrReducer:
    """_latest_str reducer always returns the newer value."""

    def test_returns_second_value(self):
        assert _latest_str("old", "new") == "new"

    def test_both_empty(self):
        assert _latest_str("", "") == ""

    def test_overwrites_with_different(self):
        assert _latest_str("parse_input", "fetch_weather") == "fetch_weather"


class TestAgentStateTypedDict:
    """AgentState construction and field access."""

    def test_minimal_state(self):
        state: AgentState = {
            "user_input": {"destination": "大理", "budget": 5000},
            "current_phase": "start",
            "error": "",
            "retry_count": 0,
        }
        assert state["user_input"]["destination"] == "大理"
        assert state["current_phase"] == "start"
        assert state["error"] == ""
        assert state["retry_count"] == 0

    def test_full_state(self):
        state: AgentState = {
            "user_input": {
                "origin": "北京",
                "destination": "大理",
                "start_date": "2026-09-01",
                "end_date": "2026-09-03",
                "budget": 5000,
                "preferences": ["浪漫", "自然"],
                "pace": "轻松",
            },
            "parsed_params": {"destination": "大理", "num_days": 2},
            "weather_data": {
                "2026-09-01": {"condition": "晴", "high": 26, "low": 16},
                "2026-09-02": {"condition": "多云", "high": 27, "low": 17},
            },
            "poi_list": [{"name": "洱海", "type": "自然", "rating": 4.8, "cost": 0}],
            "food_list": [{"name": "段公子餐厅", "cuisine": "云南菜", "rating": 4.6, "avg_cost": 80}],
            "draft_itinerary": {},
            "final_itinerary": {},
            "budget_breakdown": {},
            "couple_notes": [],
            "messages": [],
            "current_phase": "start",
            "error": "",
            "retry_count": 0,
        }
        assert len(state["weather_data"]) == 2
        assert len(state["poi_list"]) == 1

    def test_optional_fields_can_be_missing(self):
        """total=False TypedDict allows missing keys."""
        state: AgentState = {"current_phase": "start"}
        assert state.get("user_input") is None
        assert state.get("error") is None

    def test_current_phase_annotated_type(self):
        """Verify current_phase accepts string values."""
        state: AgentState = {"current_phase": "parse_input", "error": "", "retry_count": 0}
        state["current_phase"] = "fetch_weather"
        assert state["current_phase"] == "fetch_weather"
