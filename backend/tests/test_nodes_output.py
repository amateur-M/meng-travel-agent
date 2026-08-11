"""Tests for output-stage nodes: add_couple_touch, output_format."""

import pytest

from agents.state import AgentState
from agents.nodes.parse_input import parse_input
from agents.nodes.fetch_weather import fetch_weather
from agents.nodes.search_poi import search_poi
from agents.nodes.search_food import search_food
from agents.nodes.plan_itinerary import plan_itinerary
from agents.nodes.budget_check import budget_check
from agents.nodes.adapt_weather import adapt_weather
from agents.nodes.add_couple_touch import add_couple_touch, _pick_message, _TEMPLATES
from agents.nodes.output_format import output_format


# ── helpers ──────────────────────────────────────────────────────

def _full_state_through_weather(destination="大理", days=2):
    user = {
        "origin": "北京", "destination": destination,
        "start_date": "2026-09-01", "end_date": f"2026-09-0{days+1}",
        "budget": 5000, "preferences": ["浪漫", "美食"], "pace": "轻松",
    }
    state: AgentState = {"user_input": user, "current_phase": "start", "error": "", "retry_count": 0}
    state.update(parse_input(state))
    state.update(fetch_weather(state))
    state.update(search_poi(state))
    state.update(search_food(state))
    state.update(plan_itinerary(state))
    state.update(budget_check(state))
    state.update(adapt_weather(state))
    return state


# ── add_couple_touch ─────────────────────────────────────────────

class TestAddCoupleTouch:

    def test_every_activity_gets_couple_note(self):
        state = _full_state_through_weather()
        result = add_couple_touch(state)
        for day in result["draft_itinerary"]["days"]:
            for act in day["activities"]:
                assert "couple_note" in act, f"Missing couple_note in {act['name']}"
                assert len(act["couple_note"]) > 0

    def test_couple_notes_list_populated(self):
        state = _full_state_through_weather()
        result = add_couple_touch(state)
        notes = result["couple_notes"]
        assert len(notes) == len(result["draft_itinerary"]["days"])

    def test_current_phase_set(self):
        state = _full_state_through_weather()
        result = add_couple_touch(state)
        assert result["current_phase"] == "add_couple_touch"


class TestPickMessage:

    def test_pick_message_returns_non_empty_string(self):
        msg = _pick_message("洱海", "自然")
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_pick_message_contains_activity_name(self):
        msg = _pick_message("苍山", "自然")
        assert "苍山" in msg

    def test_pick_message_fallback_for_unknown_type(self):
        msg = _pick_message("未知活动", "nonexistent_type")
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_all_template_types_format_without_error(self):
        """Every template type should format correctly with a real name."""
        for act_type, templates in _TEMPLATES.items():
            for template in templates:
                # Each template should be formattable with {name}
                try:
                    result = template.format(name="测试活动")
                    assert len(result) > 0
                except KeyError as e:
                    pytest.fail(f"Template for type '{act_type}' has missing placeholder: {e}")


# ── output_format ────────────────────────────────────────────────

class TestOutputFormat:

    def test_produces_final_itinerary(self):
        state = _full_state_through_weather()
        state.update(add_couple_touch(state))
        result = output_format(state)
        final = result["final_itinerary"]
        assert "plan_id" in final
        assert len(final["plan_id"]) == 8
        assert final["destination"] == "大理"
        assert final["status"] == "completed"

    def test_final_has_all_sections(self):
        state = _full_state_through_weather()
        state.update(add_couple_touch(state))
        result = output_format(state)
        final = result["final_itinerary"]
        for key in ["plan_id", "destination", "start_date", "end_date",
                     "budget_breakdown", "days", "couple_notes", "status"]:
            assert key in final, f"Missing key: {key}"

    def test_plan_id_is_unique(self):
        state = _full_state_through_weather()
        state.update(add_couple_touch(state))
        r1 = output_format(state)
        r2 = output_format(state)
        assert r1["final_itinerary"]["plan_id"] != r2["final_itinerary"]["plan_id"]

    def test_current_phase_set(self):
        state = _full_state_through_weather()
        state.update(add_couple_touch(state))
        result = output_format(state)
        assert result["current_phase"] == "output_format"
