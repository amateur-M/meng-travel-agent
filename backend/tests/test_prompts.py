"""Tests for prompt templates (M1 compat + M2 .md templates)."""

import pytest

from prompts import (
    SYSTEM_PROMPT, ITINERARY_PROMPT, COUPLE_MESSAGE_PROMPT,
    BUDGET_CHECK_PROMPT, WEATHER_ADAPT,
    PARSE_INPUT_PROMPT, PLAN_ITINERARY_PROMPT, COUPLE_COPY_PROMPT,
    WEATHER_ADAPT_PROMPT, BUDGET_DOWNGRADE_PROMPT,
)


class TestSystemPrompt:
    def test_not_empty(self):
        assert len(SYSTEM_PROMPT) > 100

    def test_mentions_core_principles(self):
        assert len(SYSTEM_PROMPT) > 100


class TestItineraryPrompt:
    def test_has_placeholders(self):
        assert "{destination}" in ITINERARY_PROMPT
        assert "{num_days}" in ITINERARY_PROMPT
        assert "{budget}" in ITINERARY_PROMPT

    def test_formats_without_error(self):
        result = ITINERARY_PROMPT.format(
            num_days=2, destination="Dali", start_date="2026-09-01",
            end_date="2026-09-03", budget=5000, preferences="romantic",
            pace="relaxed", weather_summary="Sunny", poi_summary="POIs",
            food_summary="Foods", daily_budget=2500, extra_instructions="",
        )
        assert "Dali" in result


class TestCoupleMessagePrompt:
    def test_has_placeholders(self):
        assert "{destination}" in COUPLE_MESSAGE_PROMPT
        assert "{activity_name}" in COUPLE_MESSAGE_PROMPT
        assert "{activity_type}" in COUPLE_MESSAGE_PROMPT

    def test_formats_without_error(self):
        result = COUPLE_MESSAGE_PROMPT.format(
            destination="Dali", activity_name="Biking", activity_type="outdoor",
        )
        assert "Dali" in result


class TestBudgetCheckPrompt:
    def test_has_placeholders(self):
        assert "{budget}" in BUDGET_CHECK_PROMPT
        assert "{current_spent}" in BUDGET_CHECK_PROMPT
        assert "{itinerary_summary}" in BUDGET_CHECK_PROMPT


class TestWeatherAdaptPrompt:
    def test_has_placeholders(self):
        assert "{weather_data}" in WEATHER_ADAPT
        assert "{itinerary_summary}" in WEATHER_ADAPT

    def test_new_md_template_has_weather_keywords(self):
        assert "precip_prob" in WEATHER_ADAPT_PROMPT
        assert "> 35" in WEATHER_ADAPT_PROMPT


class TestM2PromptTemplates:
    """Verify new .md templates load correctly."""

    def test_parse_input_prompt_not_empty(self):
        assert len(PARSE_INPUT_PROMPT) > 200

    def test_plan_itinerary_prompt_not_empty(self):
        assert len(PLAN_ITINERARY_PROMPT) > 500

    def test_couple_copy_prompt_not_empty(self):
        assert len(COUPLE_COPY_PROMPT) > 200

    def test_weather_adapt_prompt_not_empty(self):
        assert len(WEATHER_ADAPT_PROMPT) > 200

    def test_budget_downgrade_prompt_not_empty(self):
        assert len(BUDGET_DOWNGRADE_PROMPT) > 200

    def test_all_m2_templates_have_placeholders(self):
        for name, tpl in [
            ("PARSE_INPUT_PROMPT", PARSE_INPUT_PROMPT),
            ("PLAN_ITINERARY_PROMPT", PLAN_ITINERARY_PROMPT),
            ("COUPLE_COPY_PROMPT", COUPLE_COPY_PROMPT),
            ("WEATHER_ADAPT_PROMPT", WEATHER_ADAPT_PROMPT),
            ("BUDGET_DOWNGRADE_PROMPT", BUDGET_DOWNGRADE_PROMPT),
        ]:
            assert "{" in tpl, f"{name} has no placeholders"
