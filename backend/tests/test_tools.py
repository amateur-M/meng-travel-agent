"""Unit tests for LangChain Tools (M2)."""

import json
import pytest
from unittest.mock import patch, MagicMock

from tools.weather_tool import (
    weather_tool_sync,
    _parse_qweather_daily,
    _parse_qweather_v1_daily,
    _forecast_days,
    _qweather_headers,
    _fetch_qweather_sync,
)
from tools.poi_search_tool import poi_search_tool
from tools.food_search_tool import food_search_tool
from tools.maps_tool import maps_tool


# ── weather_tool_sync ────────────────────────────────────────────

class TestWeatherToolSync:
    """weather_tool_sync returns a dict directly (no JSON wrapper)."""

    @pytest.fixture(autouse=True)
    def _disable_real_weather(self):
        """Force real-weather fetchers to fail so tests stay deterministic."""
        with patch("tools.weather_tool._fetch_qweather_sync", side_effect=RuntimeError("offline")), \
             patch("tools.weather_tool._fetch_openweathermap_sync", side_effect=RuntimeError("offline")):
            yield

    def test_returns_dict_with_date_keys(self):
        result = weather_tool_sync("合肥", "2026-09-01", "2026-09-03")
        assert isinstance(result, dict)
        assert len(result) == 3  # 3 days inclusive
        assert "2026-09-01" in result

    def test_each_day_has_required_fields(self):
        result = weather_tool_sync("大理", "2026-08-15", "2026-08-16")
        for day_data in result.values():
            assert "condition" in day_data
            assert "high" in day_data
            assert "low" in day_data
            assert "precip_prob" in day_data
            assert "humidity" in day_data

    def test_known_city_uses_city_patterns(self):
        result = weather_tool_sync("大理", "2026-08-15", "2026-08-15")
        d1 = list(result.values())[0]
        # Dali in August = summer
        assert d1["condition"] in ("晴", "多云", "小雨", "晴转多云")

    def test_unknown_city_falls_back_default(self):
        result = weather_tool_sync("UnknownCity", "2026-08-15", "2026-08-15")
        assert len(result) == 1
        d1 = list(result.values())[0]
        assert d1["source"] == "mock"

    def test_single_day_range(self):
        result = weather_tool_sync("大理", "2026-09-01", "2026-09-01")
        assert len(result) == 1

    def test_invalid_dates_defaults_today(self):
        result = weather_tool_sync("大理", "not-a-date", "also-bad")
        assert len(result) >= 1


# ── QWeather (和风天气) parsing & routing ─────────────────────────

class TestQWeather:
    """QWeather daily parsing and provider routing."""

    def test_parse_qweather_v1_daily(self):
        daily = [{
            "forecastStartTime": "2026-09-01T00:00+08:00",
            "temperatureMax": {"value": 29.9, "unit": "°C"},
            "temperatureMin": {"value": 20.1, "unit": "°C"},
            "temperatureAvg": {"value": 25.0, "unit": "°C"},
            "daytime": {
                "condition": {"text": "小雨", "code": "305"},
                "precipitation": {"probability": 0.64, "type": "rain"},
                "humidity": 0.52,
                "wind": {"direction": {"compass": "w"}, "scale": 2},
            },
            "nighttime": {
                "condition": {"text": "多云", "code": "101"},
                "precipitation": {"probability": 0.2},
                "humidity": 0.61,
                "wind": {"direction": {"compass": "nw"}, "scale": 1},
            },
        }]
        result = _parse_qweather_v1_daily(daily, "2026-09-01", "2026-09-01")
        day = result["2026-09-01"]
        assert day["condition"] == "小雨"
        assert day["condition_en"] == "rain"
        assert day["high"] == 29.9
        assert day["humidity"] == 52.0
        assert day["precip_prob"] == 0.64

    def test_forecast_days_clamps_to_ten(self):
        assert _forecast_days("2026-09-01", "2026-09-03") == 3
        assert _forecast_days("2026-09-01", "2026-09-30") == 10

    def test_qweather_headers_uses_bearer_token(self):
        with patch("tools.weather_tool.settings") as mock_settings:
            mock_settings.weather_api_key = "test-jwt"
            assert _qweather_headers() == {"Authorization": "Bearer test-jwt"}

    def test_parse_qweather_daily_basic(self):
        daily = [
            {"fxDate": "2026-09-01", "textDay": "晴", "textNight": "多云",
             "tempMax": "30", "tempMin": "20", "humidity": "55",
             "windDirDay": "西南风", "windScaleDay": "3-4"},
            {"fxDate": "2026-09-02", "textDay": "小雨", "textNight": "阴",
             "tempMax": "26", "tempMin": "18", "humidity": "80",
             "windDirDay": "东风", "windScaleDay": "2"},
        ]
        result = _parse_qweather_daily(daily, "2026-09-01", "2026-09-02")
        assert "2026-09-01" in result
        assert result["2026-09-01"]["source"] == "qweather"
        assert result["2026-09-01"]["condition"] == "晴"
        assert result["2026-09-01"]["high"] == 30.0
        assert result["2026-09-02"]["condition_en"] == "rain"

    def test_parse_qweather_daily_filters_out_of_range(self):
        daily = [
            {"fxDate": "2026-08-01", "textDay": "晴", "tempMax": "30", "tempMin": "20"},
            {"fxDate": "2026-09-02", "textDay": "多云", "tempMax": "26", "tempMin": "18"},
        ]
        result = _parse_qweather_daily(daily, "2026-09-01", "2026-09-02")
        assert "2026-08-01" not in result
        assert "2026-09-02" in result

    def test_parse_qweather_daily_empty_raises(self):
        with pytest.raises(ValueError):
            _parse_qweather_daily([], "2026-09-01", "2026-09-02")

    def test_sync_routes_to_qweather(self):
        fake = {"2026-09-01": {"condition": "晴", "source": "qweather"}}
        with patch("tools.weather_tool._fetch_qweather_sync", return_value=fake) as mock_fetch, \
             patch("tools.weather_tool.settings") as mock_settings:
            mock_settings.weather_provider = "qweather"
            mock_settings.weather_api_key = "test-key"
            result = weather_tool_sync("大理", "2026-09-01", "2026-09-01")
            assert result == fake
            mock_fetch.assert_called_once()

    def test_sync_falls_back_to_mock_on_unknown_city(self):
        with patch("tools.weather_tool._fetch_qweather_sync", side_effect=ValueError("unknown city")):
            result = weather_tool_sync("UnknownCity", "2026-09-01", "2026-09-01")
            assert list(result.values())[0]["source"] == "mock"


# ── poi_search_tool ──────────────────────────────────────────────

class TestPoiSearchTool:
    """poi_search_tool returns a JSON string of POI list."""

    def test_known_city_returns_pois(self):
        result = json.loads(poi_search_tool.invoke({"city": "大理", "preferences": ""}))
        assert isinstance(result, list)
        assert len(result) >= 5
        assert "name" in result[0]
        assert "couple_score" in result[0]

    def test_preferences_filter_results(self):
        all_pois = json.loads(poi_search_tool.invoke({"city": "三亚", "preferences": ""}))
        romantic_pois = json.loads(poi_search_tool.invoke({"city": "三亚", "preferences": "浪漫"}))
        # Filtered should not exceed unfiltered
        assert len(romantic_pois) <= len(all_pois)

    def test_unknown_city_fallback(self):
        result = json.loads(poi_search_tool.invoke({"city": "NowhereLand", "preferences": ""}))
        assert len(result) >= 2

    def test_poi_has_required_fields(self):
        result = json.loads(poi_search_tool.invoke({"city": "成都", "preferences": "浪漫,自然"}))
        for poi in result:
            assert "name" in poi
            assert "type" in poi
            assert "couple_score" in poi
            assert "indoor" in poi
            assert "cost" in poi


# ── food_search_tool ─────────────────────────────────────────────

class TestFoodSearchTool:
    """food_search_tool returns a JSON string of restaurant list."""

    def test_known_city_returns_restaurants(self):
        result = json.loads(food_search_tool.invoke({
            "city": "大理", "cuisine": "", "budget_per_person": 0,
        }))
        assert isinstance(result, list)
        assert len(result) >= 3
        assert "name" in result[0]
        assert "cuisine" in result[0]

    def test_budget_filter_strict(self):
        # All results must be within budget
        result = json.loads(food_search_tool.invoke({
            "city": "大理", "cuisine": "", "budget_per_person": 50,
        }))
        for r in result:
            assert r["avg_cost"] <= 50

    def test_cuisine_search_prefers_match(self):
        result = json.loads(food_search_tool.invoke({
            "city": "三亚", "cuisine": "海鲜", "budget_per_person": 0,
        }))
        assert len(result) >= 1

    def test_restaurant_has_atmosphere(self):
        result = json.loads(food_search_tool.invoke({
            "city": "大理", "cuisine": "", "budget_per_person": 0,
        }))
        for r in result:
            assert "atmosphere" in r
            assert isinstance(r["atmosphere"], list)


# ── maps_tool ────────────────────────────────────────────────────

class TestMapsTool:
    """maps_tool returns JSON string with route plan."""

    def test_two_points_returns_route(self):
        coords = json.dumps([
            {"name": "A", "lat": 25.6, "lng": 100.2},
            {"name": "B", "lat": 25.7, "lng": 100.3},
        ])
        result = json.loads(maps_tool.invoke({"coordinates": coords}))
        assert result["route"] == ["A", "B"]
        assert len(result["segments"]) == 1
        assert result["total_distance_km"] > 0

    def test_multiple_points_greedy_order(self):
        coords = json.dumps([
            {"name": "Erhai", "lat": 25.6065, "lng": 100.2299},
            {"name": "Old Town", "lat": 25.6833, "lng": 100.1620},
            {"name": "Cangshan", "lat": 25.6544, "lng": 100.1246},
        ])
        result = json.loads(maps_tool.invoke({"coordinates": coords}))
        assert len(result["route"]) == 3
        assert "Erhai" in result["route"]

    def test_single_point_no_segments(self):
        coords = json.dumps([{"name": "Solo", "lat": 25.0, "lng": 100.0}])
        result = json.loads(maps_tool.invoke({"coordinates": coords}))
        assert result["route"] == ["Solo"]
        assert result["segments"] == []

    def test_transit_modes_present(self):
        coords = json.dumps([
            {"name": "A", "lat": 25.6, "lng": 100.2},
            {"name": "B", "lat": 25.7, "lng": 100.3},
        ])
        result = json.loads(maps_tool.invoke({"coordinates": coords}))
        seg = result["segments"][0]
        assert "drive" in seg
        assert "transit" in seg
        assert "duration_min" in seg["drive"]

    def test_invalid_json_returns_error(self):
        result = json.loads(maps_tool.invoke({"coordinates": "notjson"}))
        assert "error" in result

    def test_empty_array_returns_error(self):
        result = json.loads(maps_tool.invoke({"coordinates": "[]"}))
        assert "error" in result

    def test_missing_lat_lng_returns_error(self):
        coords = json.dumps([{"name": "A"}])
        result = json.loads(maps_tool.invoke({"coordinates": coords}))
        assert "error" in result
