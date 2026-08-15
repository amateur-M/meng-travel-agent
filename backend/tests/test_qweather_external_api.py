"""Opt-in real QWeather API smoke test.

Run with:
    QWX_TEST_REAL_API=1 pytest tests/test_qweather_external_api.py -q
"""

import os
from datetime import date, timedelta

import pytest

_enabled = os.getenv("QWX_TEST_REAL_API", "").lower() in {
    "1",
    "true",
    "yes",
}

from config.settings import settings
from services.qweather_auth import build_qweather_headers
from tools.weather_tool import _fetch_qweather_sync

pytestmark = pytest.mark.skipif(
    not _enabled,
    reason="Set QWX_TEST_REAL_API=1 to hit the real QWeather API",
)


def test_real_qweather_daily_forecast():
    headers = build_qweather_headers(settings)
    assert "Authorization" in headers or "X-QW-Api-Key" in headers

    start = (date.today() + timedelta(days=1)).isoformat()
    end = (date.today() + timedelta(days=2)).isoformat()
    result = _fetch_qweather_sync("北京", start, end)

    assert result
    assert all(day["source"] == "qweather" for day in result.values())
