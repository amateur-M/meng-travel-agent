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
