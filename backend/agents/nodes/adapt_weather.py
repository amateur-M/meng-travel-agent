"""adapt_weather — Adjust itinerary for rain or extreme heat.

M2: uses the LLM via services.llm with WEATHER_ADAPT_PROMPT for
richer, context-aware adjustments. Falls back to rule-based logic
when API key is absent.
"""

import json
from typing import Dict, Any

from agents.state import AgentState
from prompts import WEATHER_ADAPT, WEATHER_ADAPT_PROMPT
from services.llm import call_llm


def _fill_prompt(template: str, **kwargs) -> str:
    """Fill template placeholders using str.replace (avoids JSON {} conflict)."""
    result = template
    for key, val in kwargs.items():
        result = result.replace("{" + key + "}", str(val))
    return result


def _format_weather_and_itinerary(state: AgentState) -> tuple:
    """Extract weather data and itinerary summary from state."""
    weather = state.get("weather_data", {})
    draft = state.get("draft_itinerary", {})

    weather_lines = []
    for d, w in weather.items():
        weather_lines.append(
            f"  {d}: {w.get('condition', '?')}，"
            f"{w.get('high', '?')}°C / {w.get('low', '?')}°C，"
            f"降水概率 {w.get('precip_prob', 0):.0%}"
        )
    weather_text = "\n".join(weather_lines) if weather_lines else "暂无天气数据"

    itin_lines = []
    for day in draft.get("days", []):
        idx = day.get("day_index", 0) + 1
        date_key = list(weather.keys())[idx - 1] if idx - 1 < len(weather) else ""
        w = weather.get(date_key, {})
        itin_lines.append(
            f"第{idx}天（{date_key}，{w.get('condition', '晴')}）："
        )
        for act in day.get("activities", []):
            itin_lines.append(
                f"  - {act.get('period', '')}：{act['name']}"
                f"（{act.get('type', '?')}，{'室内' if act.get('indoor_backup') else '室外'}）"
            )

    return weather_text, "\n".join(itin_lines)


def _rule_based_adapt(state: AgentState) -> dict:
    """Fallback: rule-based weather adaptation (M1 logic)."""
    weather = state.get("weather_data", {})
    draft = state.get("draft_itinerary", {})
    pois = state.get("poi_list", [])

    indoor_map = {p["name"]: p for p in pois if p.get("indoor")}

    for day_data in draft.get("days", []):
        day_idx = day_data.get("day_index", 0)
        date_key = list(weather.keys())[day_idx] if day_idx < len(weather) else ""
        w = weather.get(date_key, {})
        condition = w.get("condition", "晴")
        high_temp = w.get("high", 25)

        is_rain = any(kw in condition for kw in ["雨", "暴雨", "雷"])
        is_hot = high_temp > 35

        if not is_rain and not is_hot:
            continue

        for act in day_data.get("activities", []):
            start = act.get("start_time", "")
            hour = int(start.split(":")[0]) if start else 0

            if is_rain and act.get("type") not in ("室内", "留白", "美食"):
                replacement = None
                for p in pois:
                    if p.get("indoor"):
                        replacement = p
                        break
                if replacement:
                    act["name"] = replacement["name"]
                    act["type"] = replacement.get("type", "室内")
                    act["location"] = replacement.get("location", "")
                    act["indoor_backup"] = act.get("name", "")

            elif is_hot and 11 <= hour <= 15 and act.get("type") not in ("室内", "留白", "美食"):
                act["start_time"] = "08:00" if hour < 13 else "17:00"
                act["weather_note"] = "高温调整：避开正午时段"

    return draft


def _find_indoor_replacement(act: dict, indoor_map: dict, pois: list) -> dict | None:
    """Pick an indoor alternative for the given outdoor activity.

    Exported for testability; also used by _rule_based_adapt internally.
    """
    if act["name"] in indoor_map:
        return indoor_map[act["name"]]
    for p in pois:
        if p.get("indoor") and p.get("type") in ("文化",):
            return p
    for p in pois:
        if p.get("indoor"):
            return p
    return {"name": "室内咖啡馆", "type": "室内", "cost": 50, "location": "市区"}


def adapt_weather(state: AgentState) -> Dict[str, Any]:
    """Apply weather-based adjustments to the draft itinerary.

    M2: tries LLM-powered adaptation via WEATHER_ADAPT_PROMPT first.
    Falls back to rule-based logic when API key is absent.

    Returns:
        Partial state with draft_itinerary optionally modified.
    """
    weather_text, itinerary_text = _format_weather_and_itinerary(state)

    adapt_prompt = _fill_prompt(
        WEATHER_ADAPT_PROMPT,
        weather_data=weather_text,
        itinerary_summary=itinerary_text,
    )

    result = call_llm(
        system_prompt="你是一个细心的行程调整助手。",
        user_prompt=adapt_prompt,
        mock_response={"swaps": [], "time_shifts": [], "warnings": []},
    )

    draft = state.get("draft_itinerary", {})

    # Apply LLM-generated swaps if available
    swaps = result.get("swaps", [])
    if swaps:
        for swap in swaps:
            day_idx = swap.get("day_index", 0)
            if day_idx < len(draft.get("days", [])):
                day = draft["days"][day_idx]
                for act in day.get("activities", []):
                    if act["name"] == swap.get("original", {}).get("name"):
                        repl = swap.get("replacement", {})
                        act["name"] = repl.get("name", act["name"])
                        act["type"] = repl.get("type", act.get("type", "室内"))
                        act["estimated_cost"] = repl.get("estimated_cost", act.get("estimated_cost", 0))
                        act["description"] = repl.get("description", act.get("description", ""))
                        act["weather_note"] = swap.get("reason", "")
                        break
    else:
        draft = _rule_based_adapt(state)

    # Apply time shifts
    for shift in result.get("time_shifts", []):
        day_idx = shift.get("day_index", 0)
        if day_idx < len(draft.get("days", [])):
            for act in draft["days"][day_idx].get("activities", []):
                if act["name"] == shift.get("activity"):
                    act["period"] = shift.get("to_period", act["period"])
                    act["weather_note"] = shift.get("reason", "")

    return {
        "draft_itinerary": draft,
        "current_phase": "adapt_weather",
    }
