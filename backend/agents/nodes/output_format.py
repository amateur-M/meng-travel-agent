"""output_format — Final formatting node that packages the draft into final_itinerary.

Converts the internal draft dict into the shape expected by TripPlanResponse
and performs a final validation pass.
"""

import uuid
from datetime import date, timedelta
from typing import Dict, Any

from agents.state import AgentState


def _normalise_days(params: dict, draft: dict, weather: dict) -> list:
    """Fill day metadata and recompute daily totals before returning JSON."""
    try:
        start = date.fromisoformat(str(params.get("start_date", "")))
    except (ValueError, TypeError):
        start = date.today()

    weather_keys = list(weather.keys())
    normalised = []

    for index, day in enumerate(draft.get("days", [])):
        day_out = dict(day)
        day_index = int(day.get("day_index", index))
        day_out["day_index"] = day_index
        day_out["trip_date"] = (start + timedelta(days=day_index)).isoformat()

        weather_key = weather_keys[day_index] if day_index < len(weather_keys) else ""
        item = weather.get(weather_key, {})
        day_out["weather_condition"] = day_out.get(
            "weather_condition",
            day_out.get("weather", item.get("condition", "晴")),
        )
        day_out.pop("weather", None)

        if item.get("high") is not None:
            day_out["weather_high"] = float(item["high"])
        if item.get("low") is not None:
            day_out["weather_low"] = float(item["low"])

        day_out["daily_cost"] = sum(
            float(activity.get("estimated_cost", 0))
            for activity in day.get("activities", [])
        )
        normalised.append(day_out)

    return normalised


def output_format(state: AgentState) -> Dict[str, Any]:
    """Package draft_itinerary + budget_breakdown + couple_notes into final form.

    This is a pure transform node — no LLM call, no side effects.
    It ensures the output is structurally valid before the SSE stream
    emits the "complete" event.

    Returns:
        Partial state with final_itinerary ready for serialisation.
    """
    params = state.get("parsed_params", {})
    draft = state.get("draft_itinerary", {})
    budget = state.get("budget_breakdown", {})
    notes = state.get("couple_notes", [])
    weather_swaps = state.get("weather_swaps", [])
    rhythm_adjustments = state.get("rhythm_adjustments", [])
    days = _normalise_days(params, draft, state.get("weather_data", {}))

    if not budget:
        total_spent = sum(float(day["daily_cost"]) for day in days)
        budget = {
            "total_budget": params.get("budget", total_spent),
            "total_spent": total_spent,
            "by_day": [float(day["daily_cost"]) for day in days],
            "over_budget": total_spent > params.get("budget", total_spent),
            "warning_level": "over" if total_spent > params.get("budget", total_spent) else "ok",
            "spending_ratio": total_spent / max(float(params.get("budget", 1)), 1),
            "downgrade_applied": False,
            "downgrade_notes": [],
        }

    plan_id = str(uuid.uuid4())[:8]

    final = {
        "plan_id": plan_id,
        "destination": params.get("destination", ""),
        "start_date": params.get("start_date", ""),
        "end_date": params.get("end_date", ""),
        "budget_breakdown": budget,
        "days": days,
        "couple_notes": notes,
        "weather_swaps": weather_swaps,
        "rhythm_adjustments": rhythm_adjustments,
        "status": "completed",
    }

    return {
        "final_itinerary": final,
        "current_phase": "output_format",
    }
