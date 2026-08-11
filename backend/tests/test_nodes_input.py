"""Tests for input-stage nodes: parse_input, fetch_weather, search_poi, search_food."""

import pytest
from datetime import date, timedelta

from agents.state import AgentState
from agents.nodes.parse_input import parse_input
from agents.nodes.fetch_weather import fetch_weather
from agents.nodes.search_poi import search_poi
from agents.nodes.search_food import search_food


def _min_state(overrides: dict | None = None) -> AgentState:
    s: AgentState = {
        "user_input": {
            "origin": "Beijing",
            "destination": "Dali",
            "start_date": "2026-09-01",
            "end_date": "2026-09-03",
            "budget": 5000,
            "preferences": ["romantic", "food"],
            "pace": "relaxed",
        },
        "current_phase": "start",
        "error": "",
        "retry_count": 0,
    }
    if overrides:
        s.update(overrides)
    return s


class TestParseInput:

    def test_parses_all_fields(self):
        state = _min_state()
        result = parse_input(state)
        p = result["parsed_params"]
        assert p["origin"] == "Beijing"
        assert p["destination"] == "Dali"
        assert p["budget"] == 5000
        assert p["preferences"] == ["romantic", "food"]
        assert p["pace"] == "relaxed"
        assert p["num_days"] == 2
        assert result["current_phase"] == "parse_input"
        assert result["retry_count"] == 0
        assert result["error"] == ""

    def test_defaults_missing_fields(self):
        state: AgentState = {"user_input": {"destination": "Lijiang"}, "current_phase": "", "error": "", "retry_count": 0}
        result = parse_input(state)
        p = result["parsed_params"]
        assert "origin" in p
        assert p["budget"] == 3000
        assert isinstance(p["preferences"], list)

    def test_budget_cast_to_float(self):
        state: AgentState = {"user_input": {"destination": "Sanya", "budget": "8000"}, "current_phase": "", "error": "", "retry_count": 0}
        result = parse_input(state)
        assert isinstance(result["parsed_params"]["budget"], float)

    def test_num_days_single_day(self):
        state = _min_state({"user_input": {"destination": "Dali", "start_date": "2026-09-01", "end_date": "2026-09-01"}})
        result = parse_input(state)
        assert result["parsed_params"]["num_days"] == 1

    def test_num_days_fallback_on_bad_dates(self):
        state: AgentState = {"user_input": {"destination": "Dali", "start_date": "bad", "end_date": "worse"}, "current_phase": "", "error": "", "retry_count": 0}
        result = parse_input(state)
        assert result["parsed_params"]["num_days"] == 1


class TestFetchWeather:

    def test_generates_mock_weather_for_date_range(self):
        state = _min_state()
        parsed = parse_input(state)
        state_w_parsed = {**state, **parsed}
        result = fetch_weather(state_w_parsed)
        w = result["weather_data"]
        assert "2026-09-01" in w
        assert "2026-09-02" in w
        assert len(w) == 2
        assert result["current_phase"] == "fetch_weather"

    def test_weather_has_required_keys(self):
        state = _min_state()
        parsed = parse_input(state)
        state_w_parsed = {**state, **parsed}
        result = fetch_weather(state_w_parsed)
        day0 = result["weather_data"]["2026-09-01"]
        for key in ["condition", "high", "low", "humidity", "precip_prob"]:
            assert key in day0, f"Missing key: {key}"

    def test_weather_rotation_cycles_conditions(self):
        state = _min_state({
            "user_input": {"destination": "Dali", "start_date": "2026-09-01", "end_date": "2026-09-05"},
        })
        parsed = parse_input(state)
        state_w_parsed = {**state, **parsed}
        result = fetch_weather(state_w_parsed)
        assert len(result["weather_data"]) >= 4

    def test_defaults_to_today_on_bad_date(self):
        state: AgentState = {
            "parsed_params": {"start_date": "not-a-date", "num_days": 1, "destination": ""},
            "current_phase": "", "error": "", "retry_count": 0,
        }
        result = fetch_weather(state)
        assert len(result["weather_data"]) >= 1


class TestSearchPoi:

    def test_returns_pois_for_known_city(self):
        state: AgentState = {
            "parsed_params": {"destination": "Dali", "preferences": ["romantic"]},
            "current_phase": "", "error": "", "retry_count": 0,
        }
        result = search_poi(state)
        pois = result["poi_list"]
        assert len(pois) >= 2
        assert result["current_phase"] == "search_poi"

    def test_each_poi_has_expected_keys(self):
        state: AgentState = {
            "parsed_params": {"destination": "Dali", "preferences": []},
            "current_phase": "", "error": "", "retry_count": 0,
        }
        result = search_poi(state)
        for poi in result["poi_list"]:
            assert "name" in poi
            assert "type" in poi
            assert "rating" in poi or "couple_score" in poi

    def test_unknown_city_fallback(self):
        state: AgentState = {
            "parsed_params": {"destination": "NowhereCity", "preferences": []},
            "current_phase": "", "error": "", "retry_count": 0,
        }
        result = search_poi(state)
        assert len(result["poi_list"]) >= 2


class TestSearchFood:

    def test_returns_foods_for_known_city(self):
        state: AgentState = {
            "parsed_params": {"destination": "Dali", "budget": 5000, "num_days": 2},
            "current_phase": "", "error": "", "retry_count": 0,
        }
        result = search_food(state)
        foods = result["food_list"]
        assert len(foods) >= 1
        assert result["current_phase"] == "search_food"

    def test_each_food_has_expected_keys(self):
        state: AgentState = {
            "parsed_params": {"destination": "Dali", "budget": 5000, "num_days": 2},
            "current_phase": "", "error": "", "retry_count": 0,
        }
        result = search_food(state)
        for food in result["food_list"]:
            assert "name" in food
            assert "cuisine" in food
            assert "avg_cost" in food

    def test_other_city_food(self):
        state: AgentState = {
            "parsed_params": {"destination": "Lijiang", "budget": 5000, "num_days": 2},
            "current_phase": "", "error": "", "retry_count": 0,
        }
        result = search_food(state)
        assert len(result["food_list"]) >= 1
