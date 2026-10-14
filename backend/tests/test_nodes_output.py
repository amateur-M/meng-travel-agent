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


async def _full_state(destination="Dali", days=3):
    user = {
        "origin": "Beijing",
        "destination": destination,
        "start_date": "2026-09-01",
        "end_date": f"2026-09-{days:02d}",
        "budget": 5000,
        "preferences": ["romantic", "food"],
        "pace": "relaxed",
    }
    state: AgentState = {"user_input": user, "current_phase": "start", "error": "", "warnings": []}
    state.update(await parse_input(state))
    state.update(await fetch_weather(state))
    state.update(await search_poi(state))
    state.update(await search_food(state))
    state.update(await plan_itinerary(state))
    return state


class TestAddCoupleTouch:

    @pytest.mark.asyncio
    async def test_every_activity_gets_couple_note(self):
        state = await _full_state()
        result = await add_couple_touch(state)
        for day in result["draft_itinerary"]["days"]:
            for act in day["activities"]:
                assert act.get("couple_note"), f"Missing couple_note for {act['name']}"

    @pytest.mark.asyncio
    async def test_couple_notes_list_populated(self):
        state = await _full_state()
        result = await add_couple_touch(state)
        assert len(result["couple_notes"]) >= 1

    @pytest.mark.asyncio
    async def test_current_phase_set(self):
        state = await _full_state()
        result = await add_couple_touch(state)
        assert result["current_phase"] == "add_couple_touch"


class TestRestMessageByPeriod:
    """M5: 留白活动寄语按时段差异化。"""

    def test_rest_message_morning_has_morning_motif(self):
        msg = _pick_message("晨间漫步", "留白", "上午")
        assert msg  # non-empty
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
        msg = _pick_message("发呆", "留白", "")
        assert msg

    def test_period_templates_exist(self):
        assert set(_REST_TEMPLATES_BY_PERIOD.keys()) == {"上午", "下午", "晚间"}
        for period, templates in _REST_TEMPLATES_BY_PERIOD.items():
            assert len(templates) >= 1


class TestOutputFormat:

    @pytest.mark.asyncio
    async def test_produces_final_itinerary(self):
        state = await _full_state()
        state.update(await add_couple_touch(state))
        result = await output_format(state)
        assert "final_itinerary" in result
        assert result["current_phase"] == "output_format"

    @pytest.mark.asyncio
    async def test_final_has_all_sections(self):
        state = await _full_state()
        state.update(await add_couple_touch(state))
        result = await output_format(state)
        f = result["final_itinerary"]
        for key in ["destination", "start_date", "end_date", "days", "couple_notes", "rhythm_adjustments"]:
            assert key in f, f"Missing key: {key}"

    @pytest.mark.asyncio
    async def test_plan_id_is_unique(self):
        state = await _full_state()
        state.update(await add_couple_touch(state))
        r1 = await output_format(state)
        r2 = await output_format(state)
        assert r1["final_itinerary"]["plan_id"] != r2["final_itinerary"]["plan_id"]

    @pytest.mark.asyncio
    async def test_current_phase_set(self):
        state = await _full_state()
        state.update(await add_couple_touch(state))
        result = await output_format(state)
        assert result["current_phase"] == "output_format"
