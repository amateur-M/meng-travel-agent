"""Tests for output-stage nodes: add_couple_touch, output_format."""

import pytest

from agents.state import AgentState
from agents.nodes.parse_input import parse_input
from agents.nodes.fetch_weather import fetch_weather
from agents.nodes.search_poi import search_poi
from agents.nodes.search_food import search_food
from agents.nodes.plan_itinerary import plan_itinerary
from agents.nodes.add_couple_touch import add_couple_touch, _pick_message, _REST_TEMPLATES_BY_PERIOD
from agents.nodes.output_format import output_format


def _full_state(destination="Dali", days=3):
    user = {
        "origin": "Beijing",
        "destination": destination,
        "start_date": "2026-09-01",
        "end_date": f"2026-09-{days:02d}",
        "budget": 5000,
        "preferences": ["romantic", "food"],
        "pace": "relaxed",
    }
    state: AgentState = {"user_input": user, "current_phase": "start", "error": "", "warnings": [], "retry_count": 0}
    state.update(parse_input(state))
    state.update(fetch_weather(state))
    state.update(search_poi(state))
    state.update(search_food(state))
    state.update(plan_itinerary(state))
    return state


class TestAddCoupleTouch:

    def test_every_activity_gets_couple_note(self):
        state = _full_state()
        result = add_couple_touch(state)
        for day in result["draft_itinerary"]["days"]:
            for act in day["activities"]:
                assert act.get("couple_note"), f"Missing couple_note for {act['name']}"

    def test_couple_notes_list_populated(self):
        state = _full_state()
        result = add_couple_touch(state)
        assert len(result["couple_notes"]) >= 1

    def test_current_phase_set(self):
        state = _full_state()
        result = add_couple_touch(state)
        assert result["current_phase"] == "add_couple_touch"


class TestRestMessageByPeriod:
    """M5: 留白活动寄语按时段差异化。"""

    def test_rest_message_morning_has_morning_motif(self):
        msg = _pick_message("晨间漫步", "留白", "上午")
        assert msg  # non-empty
        # 晨光/早晨/慢慢醒 等意象二选一命中
        assert any(kw in msg for kw in ("晨", "早晨", "慢慢醒", "开始"))

    def test_rest_message_evening_has_night_motif(self):
        msg = _pick_message("夜色漫步", "留白", "晚间")
        assert msg
        assert any(kw in msg for kw in ("夜", "灯火", "星", "夜晚"))

    def test_rest_message_afternoon_default(self):
        msg = _pick_message("午后发呆", "留白", "下午")
        assert msg
        assert any(kw in msg for kw in ("午后", "阳光", "发呆", "珍惜"))

    def test_rest_without_period_falls_back_to_general(self):
        # period 为空时回退到通用留白模板
        msg = _pick_message("发呆", "留白", "")
        assert msg  # 通用模板仍返回非空

    def test_period_templates_exist(self):
        assert set(_REST_TEMPLATES_BY_PERIOD.keys()) == {"上午", "下午", "晚间"}
        for period, templates in _REST_TEMPLATES_BY_PERIOD.items():
            assert len(templates) >= 1


class TestOutputFormat:

    def test_produces_final_itinerary(self):
        state = _full_state()
        state.update(add_couple_touch(state))
        result = output_format(state)
        assert "final_itinerary" in result
        assert result["current_phase"] == "output_format"

    def test_final_has_all_sections(self):
        state = _full_state()
        state.update(add_couple_touch(state))
        result = output_format(state)
        f = result["final_itinerary"]
        for key in ["destination", "start_date", "end_date", "days", "couple_notes", "rhythm_adjustments"]:
            assert key in f, f"Missing key: {key}"

    def test_plan_id_is_unique(self):
        state = _full_state()
        state.update(add_couple_touch(state))
        r1 = output_format(state)
        r2 = output_format(state)
        assert r1["final_itinerary"]["plan_id"] != r2["final_itinerary"]["plan_id"]

    def test_current_phase_set(self):
        state = _full_state()
        state.update(add_couple_touch(state))
        result = output_format(state)
        assert result["current_phase"] == "output_format"
