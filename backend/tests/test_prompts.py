"""Tests for prompt templates (M2 .md templates + shared fill_prompt utility).

Tidy: tests for removed M1 inline templates (ITINERARY_PROMPT,
COUPLE_MESSAGE_PROMPT, BUDGET_CHECK_PROMPT, WEATHER_ADAPT) deleted
alongside the dead code they referenced.
"""

import pytest

from prompts import (
    SYSTEM_PROMPT,
    PARSE_INPUT_PROMPT, PLAN_ITINERARY_PROMPT, COUPLE_COPY_PROMPT,
    WEATHER_ADAPT_PROMPT, BUDGET_DOWNGRADE_PROMPT,
    fill_prompt,
)


class TestSystemPrompt:
    def test_not_empty(self):
        assert len(SYSTEM_PROMPT) > 100

    def test_mentions_core_principles(self):
        assert len(SYSTEM_PROMPT) > 100


class TestFillPrompt:
    """Tidy: fill_prompt is now a shared utility in the prompts package."""

    def test_replaces_placeholders(self):
        result = fill_prompt("Hello {name}, welcome to {place}!", name="Alice", place="Dali")
        assert result == "Hello Alice, welcome to Dali!"

    def test_leaves_unknown_placeholders(self):
        result = fill_prompt("{known} and {unknown}", known="yes")
        assert result == "yes and {unknown}"

    def test_handles_json_braces(self):
        tpl = 'Output JSON: {{"key": "{val}"}}'
        result = fill_prompt(tpl, val="hello")
        assert '"hello"' in result


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
