"""Tests for prompt templates — existence and formatting."""

import pytest
from prompts import (
    SYSTEM_PROMPT,
    ITINERARY_PROMPT,
    COUPLE_MESSAGE_PROMPT,
    BUDGET_CHECK_PROMPT,
    WEATHER_ADAPT_PROMPT,
)


class TestSystemPrompt:
    """System prompt defines agent role and output contract."""

    def test_non_empty(self):
        assert len(SYSTEM_PROMPT) > 50

    def test_mentions_couple_travel(self):
        assert "情侣" in SYSTEM_PROMPT

    def test_specifies_json_format(self):
        assert "JSON" in SYSTEM_PROMPT or "json" in SYSTEM_PROMPT

    def test_includes_core_principles(self):
        for keyword in ["浪漫", "预算", "天气", "情侣"]:
            assert keyword in SYSTEM_PROMPT, f"Missing keyword: {keyword}"


class TestItineraryPrompt:
    """Itinerary prompt uses str.format() with expected placeholders."""

    def test_has_all_placeholders(self):
        placeholders = [
            "{num_days}", "{destination}", "{start_date}", "{end_date}",
            "{budget}", "{preferences}", "{pace}",
            "{weather_summary}", "{poi_summary}", "{food_summary}",
            "{daily_budget}", "{extra_instructions}",
        ]
        for ph in placeholders:
            assert ph in ITINERARY_PROMPT, f"Missing placeholder: {ph}"

    def test_formats_without_error(self):
        result = ITINERARY_PROMPT.format(
            num_days=2,
            destination="大理",
            start_date="2026-09-01",
            end_date="2026-09-02",
            budget=5000,
            preferences="浪漫、美食",
            pace="轻松",
            weather_summary="  2026-09-01: 晴",
            poi_summary="  1. 洱海",
            food_summary="  1. 段公子餐厅",
            daily_budget=2500,
            extra_instructions="每天留白。",
        )
        assert "大理" in result
        assert "5000" in result
        assert "洱海" in result
        assert "段公子餐厅" in result


class TestCoupleMessagePrompt:
    """Couple message prompt for single-activity message generation."""

    def test_has_placeholders(self):
        assert "{destination}" in COUPLE_MESSAGE_PROMPT
        assert "{activity_name}" in COUPLE_MESSAGE_PROMPT
        assert "{activity_type}" in COUPLE_MESSAGE_PROMPT

    def test_formats_without_error(self):
        result = COUPLE_MESSAGE_PROMPT.format(
            destination="大理",
            activity_name="洱海骑行",
            activity_type="户外",
        )
        assert "大理" in result
        assert "洱海骑行" in result


class TestBudgetCheckPrompt:
    """Budget check prompt for budget validation."""

    def test_has_placeholders(self):
        assert "{budget}" in BUDGET_CHECK_PROMPT
        assert "{current_spent}" in BUDGET_CHECK_PROMPT
        assert "{itinerary_summary}" in BUDGET_CHECK_PROMPT


class TestWeatherAdaptPrompt:
    """Weather adaptation prompt."""

    def test_has_placeholders(self):
        assert "{weather_data}" in WEATHER_ADAPT_PROMPT
        assert "{itinerary_summary}" in WEATHER_ADAPT_PROMPT

    def test_mentions_rain_and_heat(self):
        assert "雨" in WEATHER_ADAPT_PROMPT
        assert "35°C" in WEATHER_ADAPT_PROMPT
