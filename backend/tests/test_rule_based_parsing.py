"""Rule-based (no-API-key) parsing: the phrases a real user actually types.

This path is what runs when no LLM key is configured — in CI, in demos, and on
any machine that has not set one up. It is also the fallback that decides whether
the chat can even offer to plan, so a gap here is a dead end for the user rather
than a cosmetic issue: "想去大理玩三天" used to stay stuck on "还差出发日期、
返程日期" forever because the day count only matched Arabic numerals.
"""

from datetime import date, timedelta

import pytest

from agents.conversation import (
    _clean_destination,
    _extract_date_range,
    _extract_modify_patch,
    _mock_handle,
    _normalise_budget,
)


class TestDestinationCleaning:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("大理玩三天", "大理"),
            ("大理玩3天", "大理"),
            ("大理", "大理"),
            ("新疆玩十天", "新疆"),
            ("天山", "天山"),  # no numeral -> untouched
            ("三亚", "三亚"),
            ("大理呆两天", "大理"),
        ],
    )
    def test_trailing_duration_and_verb_are_stripped(self, raw, expected):
        assert _clean_destination(raw) == expected

    def test_verb_alone_is_stripped(self):
        assert _clean_destination("大理玩玩") == "大理"

    def test_empty_result_falls_back_to_the_original(self):
        """Never turn a destination into an empty string."""
        assert _clean_destination("玩三天") == "玩三天"


class TestDayCount:
    def test_chinese_numeral_reaches_ready(self):
        result = _mock_handle("想去大理玩三天，预算5000元", {})
        assert result["intent"] == "planning_ready"
        assert result["slots"]["start_date"] == date.today().isoformat()
        assert result["slots"]["end_date"] == (
            date.today() + timedelta(days=2)
        ).isoformat()

    def test_arabic_numeral_still_works(self):
        result = _mock_handle("想去大理玩3天，预算5000元", {})
        assert result["intent"] == "planning_ready"

    def test_the_destination_is_not_polluted_by_the_duration(self):
        result = _mock_handle("想去大理玩三天，预算5000元", {})
        assert result["slots"]["destination"] == "大理"

    def test_a_missing_day_count_still_asks_for_dates(self):
        result = _mock_handle("想去大理，预算5000元", {})
        assert result["intent"] == "planning_intent"
        assert "日期" in result["reply"]


class TestBudgetNormalisation:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("5000", 5000.0),
            ("5,000", 5000.0),
            ("5千", 5000.0),
            ("1.5万", 15000.0),
            ("五千", 5000.0),
            ("一万", 10000.0),
            ("一万二", 12000.0),  # idiomatic for 12000
            ("八千", 8000.0),
            ("三百", 300.0),
            ("abc", 0.0),
            ("", 0.0),
        ],
    )
    def test_expressions(self, text, expected):
        assert _normalise_budget(text) == expected

    def test_numeric_input_passes_through(self):
        assert _normalise_budget(3000) == 3000.0

    @pytest.mark.parametrize(
        "message",
        ["想去大理玩三天，预算五千", "想去大理玩三天，预算5000元", "从北京出发，想去大理玩3天，预算五千"],
    )
    def test_chinese_budget_reaches_ready(self, message):
        result = _mock_handle(message, {})
        assert result["intent"] == "planning_ready", result["reply"]
        assert result["slots"]["budget"] == 5000.0


class TestExplicitDateRanges:
    def test_iso_range(self):
        assert _extract_date_range("2026-09-01 到 2026-09-03") == (
            "2026-09-01",
            "2026-09-03",
        )

    def test_chinese_range_keeps_the_month_and_day(self):
        parsed = _extract_date_range("9月1日到9月3日")
        assert parsed is not None
        start, end = parsed
        assert start.endswith("-09-01") and end.endswith("-09-03")

    def test_a_past_range_rolls_to_next_year(self):
        """A trip planner should not offer a date that has already passed."""
        start, end = _extract_date_range("1月1日到1月3日")
        assert date.fromisoformat(start) > date.today()
        assert date.fromisoformat(end) > date.today()

    def test_a_range_crossing_new_year_is_ordered(self):
        start, end = _extract_date_range("12月28日到1月3日")
        assert date.fromisoformat(start) < date.fromisoformat(end)

    def test_a_single_date_is_not_a_range(self):
        assert _extract_date_range("9月1日") is None

    def test_no_dates(self):
        assert _extract_date_range("想去大理") is None

    def test_an_explicit_range_wins_over_a_day_count(self):
        result = _mock_handle("想去大理玩3天，9月1日到9月3日，预算5000元", {})
        assert result["slots"]["start_date"].endswith("-09-01")
        assert result["slots"]["end_date"].endswith("-09-03")


class TestModifyPatch:
    SLOTS = {
        "origin": "北京",
        "destination": "大理",
        "start_date": "2026-10-16",
        "end_date": "2026-10-18",
        "budget": 5000,
    }

    def test_chinese_budget_increase(self):
        assert _extract_modify_patch("预算加到八千", self.SLOTS) == {"budget": 8000.0}

    def test_arabic_budget_increase(self):
        assert _extract_modify_patch("预算改成1万", self.SLOTS) == {"budget": 10000.0}

    def test_day_shift_is_applied_to_the_end_date(self):
        patch = _extract_modify_patch("再加一天", self.SLOTS)
        assert patch == {"end_date": "2026-10-19"}

    def test_destination_change_for_a_numeric_place_name_does_not_invent_a_budget(self):
        """Regression: "改成三亚" once parsed 三 as a budget of 3 yuan."""
        patch = _extract_modify_patch("改成三亚", self.SLOTS)
        assert patch == {"destination": "三亚"}
        assert "budget" not in patch

    def test_destination_and_budget_together(self):
        assert _extract_modify_patch("改成三亚，预算八千", self.SLOTS) == {
            "destination": "三亚",
            "budget": 8000.0,
        }

    def test_a_bare_budget_restatement_is_not_a_destination(self):
        patch = _extract_modify_patch("预算五千", self.SLOTS)
        assert patch == {"budget": 5000.0}
