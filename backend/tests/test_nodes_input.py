"""Tests for input-stage nodes: parse_input, fetch_weather, search_poi, search_food."""

import pytest
from datetime import date, timedelta
from unittest.mock import patch

from agents.state import AgentState
from agents.nodes.parse_input import parse_input
from agents.nodes.fetch_weather import fetch_weather
from agents.nodes.search_poi import search_poi
from agents.nodes.search_food import search_food


RAW_ATTRACTIONS = [
    {
        "name": "大理古城",
        "typecode": "110202",
        "type": "风景名胜;风景名胜;国家级景点",
        "address": "大理市复兴路111号",
        "business_area": "大理古城",
        "location": "100.1620,25.6833",
        "biz_ext": {"rating": "4.7", "cost": []},
        "keytag": "国家级景点",
        "photos": [],
    },
    {
        "name": "大理州博物馆",
        "typecode": "140100",
        "type": "科教文化服务;博物馆;博物馆",
        "address": "大理市下关洱河南路",
        "business_area": "下关",
        "location": "100.2200,25.6000",
        "biz_ext": {"rating": "4.5"},
        "photos": [],
    },
]


RAW_RESTAURANTS = [
    {
        "name": "古城人家",
        "typecode": "050100",
        "type": "餐饮服务;中餐厅;中餐厅",
        "address": "大理市人民路",
        "business_area": "大理古城",
        "location": "100.1620,25.6833",
        "biz_ext": {"cost": "80.00", "rating": "4.6"},
        "keytag": "本地老店",
    },
]


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
        assert p["num_days"] == 3
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
        assert "2026-09-03" in w
        assert len(w) == 3
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
        with patch("services.amap.search_pois", return_value=RAW_ATTRACTIONS):
            result = search_poi(state)
        pois = result["poi_list"]
        assert len(pois) >= 2
        assert result["current_phase"] == "search_poi"
        assert result["error"] == ""

    def test_each_poi_has_expected_keys(self):
        state: AgentState = {
            "parsed_params": {"destination": "Dali", "preferences": []},
            "current_phase": "", "error": "", "retry_count": 0,
        }
        with patch("services.amap.search_pois", return_value=RAW_ATTRACTIONS):
            result = search_poi(state)
        for poi in result["poi_list"]:
            assert "name" in poi
            assert "type" in poi
            assert "rating" in poi or "couple_score" in poi

    def test_sets_error_when_amap_fails(self):
        state: AgentState = {
            "parsed_params": {"destination": "Dali", "preferences": []},
            "current_phase": "", "error": "", "retry_count": 0,
        }
        with patch("services.amap.search_pois", side_effect=RuntimeError("no key")):
            result = search_poi(state)
        assert result["poi_list"] == []
        assert "景点搜索失败" in result["error"]


class TestSearchFood:

    def test_returns_foods_for_known_city(self):
        state: AgentState = {
            "parsed_params": {"destination": "Dali", "budget": 5000, "num_days": 2},
            "current_phase": "", "error": "", "retry_count": 0,
        }
        with patch("services.amap.search_pois", return_value=RAW_RESTAURANTS):
            result = search_food(state)
        foods = result["food_list"]
        assert len(foods) >= 1
        assert result["current_phase"] == "search_food"
        assert result["error"] == ""

    def test_each_food_has_expected_keys(self):
        state: AgentState = {
            "parsed_params": {"destination": "Dali", "budget": 5000, "num_days": 2},
            "current_phase": "", "error": "", "retry_count": 0,
        }
        with patch("services.amap.search_pois", return_value=RAW_RESTAURANTS):
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
        with patch("services.amap.search_pois", return_value=RAW_RESTAURANTS):
            result = search_food(state)
        assert len(result["food_list"]) >= 1
