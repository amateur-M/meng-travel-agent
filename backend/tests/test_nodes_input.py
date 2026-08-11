"""Tests for input-stage nodes: parse_input, fetch_weather, search_poi, search_food."""

import pytest
from datetime import date, timedelta

from agents.state import AgentState
from agents.nodes.parse_input import parse_input
from agents.nodes.fetch_weather import fetch_weather
from agents.nodes.search_poi import search_poi
from agents.nodes.search_food import search_food


# ── helpers ──────────────────────────────────────────────────────

def _min_state(overrides: dict | None = None) -> AgentState:
    s: AgentState = {
        "user_input": {
            "origin": "北京",
            "destination": "大理",
            "start_date": "2026-09-01",
            "end_date": "2026-09-03",
            "budget": 5000,
            "preferences": ["浪漫", "美食"],
            "pace": "轻松",
        },
        "current_phase": "start",
        "error": "",
        "retry_count": 0,
    }
    if overrides:
        s.update(overrides)
    return s


# ── parse_input ──────────────────────────────────────────────────

class TestParseInput:

    def test_parses_all_fields(self):
        state = _min_state()
        result = parse_input(state)
        p = result["parsed_params"]
        assert p["origin"] == "北京"
        assert p["destination"] == "大理"
        assert p["budget"] == 5000
        assert p["preferences"] == ["浪漫", "美食"]
        assert p["pace"] == "轻松"
        assert p["num_days"] == 2  # 09-01 to 09-03 = 2 days
        assert result["current_phase"] == "parse_input"
        assert result["retry_count"] == 0
        assert result["error"] == ""

    def test_defaults_missing_fields(self):
        state: AgentState = {"user_input": {"destination": "丽江"}, "current_phase": "", "error": "", "retry_count": 0}
        result = parse_input(state)
        p = result["parsed_params"]
        assert p["origin"] == "未指定"
        assert p["budget"] == 3000
        assert p["preferences"] == ["浪漫", "美食"]
        assert p["pace"] == "轻松"

    def test_budget_cast_to_float(self):
        state: AgentState = {"user_input": {"destination": "三亚", "budget": "8000"}, "current_phase": "", "error": "", "retry_count": 0}
        result = parse_input(state)
        assert isinstance(result["parsed_params"]["budget"], float)
        assert result["parsed_params"]["budget"] == 8000.0

    def test_num_days_single_day(self):
        state = _min_state({"user_input": {"destination": "大理", "start_date": "2026-09-01", "end_date": "2026-09-01"}})
        result = parse_input(state)
        assert result["parsed_params"]["num_days"] == 1  # min is 1

    def test_num_days_fallback_on_bad_dates(self):
        state: AgentState = {"user_input": {"destination": "大理", "start_date": "bad", "end_date": "worse"}, "current_phase": "", "error": "", "retry_count": 0}
        result = parse_input(state)
        assert result["parsed_params"]["num_days"] == 1  # default


# ── fetch_weather ────────────────────────────────────────────────

class TestFetchWeather:

    def test_generates_mock_weather_for_date_range(self):
        state = _min_state()
        parsed = parse_input(state)
        state_w_parsed = {**state, **parsed}
        result = fetch_weather(state_w_parsed)
        w = result["weather_data"]
        assert "2026-09-01" in w
        assert "2026-09-02" in w
        assert len(w) == 2  # 2 days
        assert result["current_phase"] == "fetch_weather"

    def test_weather_has_required_keys(self):
        state = _min_state()
        parsed = parse_input(state)
        state_w_parsed = {**state, **parsed}
        result = fetch_weather(state_w_parsed)
        day0 = result["weather_data"]["2026-09-01"]
        for key in ["condition", "high", "low", "humidity", "wind"]:
            assert key in day0

    def test_weather_rotation_cycles_conditions(self):
        state = _min_state({
            "user_input": {"destination": "大理", "start_date": "2026-09-01", "end_date": "2026-09-05"},
        })
        parsed = parse_input(state)
        state_w_parsed = {**state, **parsed}
        result = fetch_weather(state_w_parsed)
        # should have 4 days (09-01 to 09-05)
        assert len(result["weather_data"]) >= 4

    def test_defaults_to_today_on_bad_date(self):
        state: AgentState = {
            "parsed_params": {"start_date": "not-a-date", "num_days": 1},
            "current_phase": "", "error": "", "retry_count": 0,
        }
        result = fetch_weather(state)
        assert len(result["weather_data"]) == 1


# ── search_poi ───────────────────────────────────────────────────

class TestSearchPoi:

    def test_returns_dali_mock_pois(self):
        state = _min_state()
        parsed = parse_input(state)
        state_w_parsed = {**state, **parsed}
        result = search_poi(state_w_parsed)
        pois = result["poi_list"]
        assert len(pois) > 0
        names = [p["name"] for p in pois]
        assert "洱海" in names
        assert result["current_phase"] == "search_poi"

    def test_each_poi_has_expected_keys(self):
        state = _min_state()
        parsed = parse_input(state)
        state_w_parsed = {**state, **parsed}
        result = search_poi(state_w_parsed)
        for p in result["poi_list"]:
            for key in ["name", "type", "rating", "cost", "location", "indoor"]:
                assert key in p, f"Missing key '{key}' in POI: {p}"

    def test_returns_generic_pois_for_unknown_destination(self):
        state = _min_state({"user_input": {"destination": "火星"}})
        parsed = parse_input(state)
        state_w_parsed = {**state, **parsed}
        result = search_poi(state_w_parsed)
        assert len(result["poi_list"]) > 0
        assert "火星" in result["poi_list"][0]["name"]

    def test_filters_by_culture_preference(self):
        # With culture preference, non-culture/humanities/nature should be filtered
        state = _min_state({"user_input": {"destination": "大理", "preferences": ["文化"]}})
        parsed = parse_input(state)
        state_w_parsed = {**state, **parsed}
        result = search_poi(state_w_parsed)
        for p in result["poi_list"]:
            assert p["type"] in ("文化", "人文", "自然")


# ── search_food ──────────────────────────────────────────────────

class TestSearchFood:

    def test_returns_dali_mock_foods(self):
        state = _min_state()
        parsed = parse_input(state)
        state_w_parsed = {**state, **parsed}
        result = search_food(state_w_parsed)
        foods = result["food_list"]
        assert len(foods) > 0
        names = [f["name"] for f in foods]
        assert "段公子餐厅" in names
        assert result["current_phase"] == "search_food"

    def test_each_food_has_expected_keys(self):
        state = _min_state()
        parsed = parse_input(state)
        state_w_parsed = {**state, **parsed}
        result = search_food(state_w_parsed)
        for f in result["food_list"]:
            for key in ["name", "cuisine", "rating", "avg_cost", "location"]:
                assert key in f, f"Missing key '{key}' in food: {f}"

    def test_returns_generic_foods_for_unknown_destination(self):
        state = _min_state({"user_input": {"destination": "木星"}})
        parsed = parse_input(state)
        state_w_parsed = {**state, **parsed}
        result = search_food(state_w_parsed)
        assert len(result["food_list"]) > 0
        assert "木星" in result["food_list"][0]["name"]

    def test_lijiang_food(self):
        state = _min_state({"user_input": {"destination": "丽江"}})
        parsed = parse_input(state)
        state_w_parsed = {**state, **parsed}
        result = search_food(state_w_parsed)
        names = [f["name"] for f in result["food_list"]]
        assert "阿妈腊排骨" in names
