"""Shared pytest fixtures."""

import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def _disable_external_apis(monkeypatch):
    """Keep tests deterministic by disabling all external API credentials."""
    monkeypatch.setattr("config.settings.settings.openai_api_key", "")
    monkeypatch.setattr("config.settings.settings.deepseek_api_key", "")
    monkeypatch.setattr("config.settings.settings.qwen_api_key", "")
    monkeypatch.setattr("config.settings.settings.kimi_api_key", "")
    monkeypatch.setattr("config.settings.settings.weather_api_key", "")
    monkeypatch.setattr("config.settings.settings.maps_api_key", "")

    # Extra guard: make any accidental weather fetch fail immediately.
    with patch(
        "tools.weather_tool._fetch_qweather_sync",
        side_effect=RuntimeError("network disabled in tests"),
    ), patch(
        "tools.weather_tool._fetch_openweathermap_sync",
        side_effect=RuntimeError("network disabled in tests"),
    ):
        yield
