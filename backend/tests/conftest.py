"""Shared pytest fixtures."""

import os

import pytest


RUN_QWEATHER_API_TESTS = os.getenv("QWX_TEST_REAL_API", "").lower() in {
    "1",
    "true",
    "yes",
}


@pytest.fixture(autouse=True)
def _disable_external_apis(monkeypatch):
    """Keep tests deterministic by disabling all external API credentials."""
    monkeypatch.setattr("config.settings.settings.openai_api_key", "")
    monkeypatch.setattr("config.settings.settings.deepseek_api_key", "")
    monkeypatch.setattr("config.settings.settings.qwen_api_key", "")
    monkeypatch.setattr("config.settings.settings.kimi_api_key", "")
    if not RUN_QWEATHER_API_TESTS:
        monkeypatch.setattr("config.settings.settings.weather_api_key", "")
    monkeypatch.setattr("config.settings.settings.maps_api_key", "")
    yield


@pytest.fixture(autouse=True)
def _fake_amap_http(monkeypatch):
    """Keep Amap-dependent tests offline with representative API responses."""

    def fake_search_pois(city, types, offset=20):
        if "050000" in types:
            return [
                {
                    "name": "古城人家",
                    "typecode": "050100",
                    "type": "餐饮服务;中餐厅;中餐厅",
                    "address": "大理市人民路",
                    "business_area": "大理古城",
                    "location": "100.1620,25.6833",
                    "biz_ext": {"cost": "80.00", "rating": "4.6"},
                    "keytag": "本地老店",
                }
            ]
        return [
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

    def fake_driving_route(origin, destination):
        return {"distance": "12115", "duration": "1264"}

    monkeypatch.setattr("services.amap.search_pois", fake_search_pois)
    monkeypatch.setattr("services.amap.driving_route", fake_driving_route)
    yield
