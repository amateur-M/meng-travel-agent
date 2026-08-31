"""Unit tests for LangChain Tools (M2)."""

import json
import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from config.settings import settings
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
    {
        "name": "海景火锅",
        "typecode": "050100",
        "type": "餐饮服务;火锅店;火锅店",
        "address": "大理市双廊镇",
        "business_area": "双廊",
        "location": "100.2000,25.9000",
        "biz_ext": {"cost": "120.00", "rating": "4.4"},
        "keytag": "火锅",
    },
]


# ── weather_tool_sync ────────────────────────────────────────────

class TestWeatherToolSync:
    """weather_tool_sync returns a dict directly (no JSON wrapper)."""

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

    def test_forecast_days_counts_from_today_to_end(self):
        near_end = (date.today() + timedelta(days=2)).isoformat()
        far_end = (date.today() + timedelta(days=20)).isoformat()
        assert _forecast_days("2020-01-01", near_end) == 3
        assert _forecast_days("2020-01-01", far_end) == 10
        assert _forecast_days("2026-09-01", "2020-01-01") == 1

    def test_qweather_headers_uses_bearer_token(self):
        with patch(
            "tools.weather_tool.build_qweather_headers",
            return_value={"Authorization": "Bearer test-jwt"},
        ) as mock_headers:
            assert _qweather_headers() == {"Authorization": "Bearer test-jwt"}
            mock_headers.assert_called_once_with(settings)

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
    """poi_search_tool normalises live Amap attractions."""

    def _search(self, preferences=""):
        with patch("services.amap.search_pois", return_value=RAW_ATTRACTIONS):
            return json.loads(
                poi_search_tool.invoke({"city": "大理", "preferences": preferences})
            )

    def test_returns_normalised_pois(self):
        pois = self._search()
        assert len(pois) == 2
        assert pois[0]["name"] == "大理古城"
        assert "couple_score" in pois[0]

    def test_preferences_boost_matching_type(self):
        pois = self._search(preferences="文化")
        assert pois[0]["type"] == "文化"

    def test_poi_has_expected_keys(self):
        for poi in self._search(preferences="浪漫,自然"):
            for key in [
                "name",
                "type",
                "rating",
                "cost",
                "location",
                "indoor",
                "couple_score",
                "duration_min",
                "description",
            ]:
                assert key in poi


# ── food_search_tool ─────────────────────────────────────────────

class TestFoodSearchTool:
    """food_search_tool normalises live Amap restaurants."""

    def _search(self, cuisine="不限", budget_per_person=0):
        with patch("services.amap.search_pois", return_value=RAW_RESTAURANTS):
            return json.loads(
                food_search_tool.invoke({
                    "city": "大理",
                    "cuisine": cuisine,
                    "budget_per_person": budget_per_person,
                })
            )

    def test_returns_normalised_restaurants(self):
        foods = self._search()
        assert len(foods) == 2
        names = {food["name"] for food in foods}
        assert names == {"古城人家", "海景火锅"}
        by_name = {food["name"]: food for food in foods}
        assert by_name["古城人家"]["cuisine"] == "中餐"
        assert by_name["古城人家"]["avg_cost"] == 80.0
        assert isinstance(by_name["古城人家"]["atmosphere"], list)

    def test_budget_filter_strict(self):
        foods = self._search(budget_per_person=90)
        assert len(foods) == 1
        assert all(food["avg_cost"] <= 90 for food in foods)

    def test_cuisine_search_prefers_match(self):
        foods = self._search(cuisine="火锅")
        assert foods[0]["cuisine"] == "火锅"


# ── maps_tool ────────────────────────────────────────────────────

class TestMapsTool:
    """maps_tool returns a real Amap driving route."""

    def _route(self, coordinates):
        with patch(
            "services.amap.driving_route",
            return_value={"distance": "12115", "duration": "1264"},
        ):
            return json.loads(maps_tool.invoke({"coordinates": coordinates}))

    def test_two_points_returns_route(self):
        coords = json.dumps([
            {"name": "A", "lat": 25.6, "lng": 100.2},
            {"name": "B", "lat": 25.7, "lng": 100.3},
        ])
        result = self._route(coords)
        assert result["route"] == ["A", "B"]
        assert len(result["segments"]) == 1
        assert result["segments"][0]["distance_km"] == 12.1
        assert result["segments"][0]["drive"]["duration_min"] == 21

    def test_multiple_points_order(self):
        coords = json.dumps([
            {"name": "Erhai", "lat": 25.6065, "lng": 100.2299},
            {"name": "Old Town", "lat": 25.6833, "lng": 100.1620},
            {"name": "Cangshan", "lat": 25.6544, "lng": 100.1246},
        ])
        result = self._route(coords)
        assert len(result["route"]) == 3
        assert len(result["segments"]) == 2
        assert "Erhai" in result["route"]

    def test_single_point_no_segments(self):
        coords = json.dumps([{"name": "Solo", "lat": 25.0, "lng": 100.0}])
        result = json.loads(maps_tool.invoke({"coordinates": coords}))
        assert result["route"] == ["Solo"]
        assert result["segments"] == []

    def test_drive_mode_present(self):
        coords = json.dumps([
            {"name": "A", "lat": 25.6, "lng": 100.2},
            {"name": "B", "lat": 25.7, "lng": 100.3},
        ])
        result = self._route(coords)
        seg = result["segments"][0]
        assert "drive" in seg
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
