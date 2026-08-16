"""VCR cassette tests for QWeather external API integrations.

These tests replay pre-recorded HTTP interactions and never require real
credentials or network access.
"""

import importlib
from pathlib import Path

import pytest
import vcr

from config.settings import settings


weather_tool_module = importlib.import_module("tools.weather_tool")


CASSETTE_DIR = Path(__file__).parent / "cassettes"


def _vcr() -> vcr.VCR:
    return vcr.VCR(
        cassette_library_dir=str(CASSETTE_DIR),
        record_mode="none",
        filter_headers=[
            ("authorization", "DUMMY"),
            ("x-qw-api-key", "DUMMY"),
        ],
        match_on=["method", "scheme", "host", "port", "path", "query"],
    )


@pytest.fixture(autouse=True)
def _offline_qweather(monkeypatch):
    """Use dummy auth so cassette replay does not depend on .env credentials."""
    monkeypatch.setattr(settings, "weather_api_key", "test-key")
    monkeypatch.setattr(
        weather_tool_module,
        "_qweather_headers",
        lambda: {"Authorization": "Bearer DUMMY"},
    )


def test_qweather_city_lookup_cassette():
    with _vcr().use_cassette("qweather_city_lookup.yaml"):
        lat, lon = weather_tool_module._lookup_qweather_city_sync("北京")

    assert lat == pytest.approx(39.90499, abs=1e-3)
    assert lon == pytest.approx(116.40529, abs=1e-3)


def test_qweather_daily_forecast_cassette():
    start = "2026-08-17"
    end = "2026-08-18"

    with _vcr().use_cassette("qweather_daily_forecast.yaml"):
        result = weather_tool_module._fetch_qweather_sync("北京", start, end)

    assert result
    assert all(day["source"] == "qweather" for day in result.values())
