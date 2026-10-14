"""adapt_weather — Adjust itinerary for rain or extreme heat.

M2/M4: the LLM path is kept for richer suggestions, while a deterministic
rule-based path guarantees that rainy and hot days are actually adjusted even
when no provider key is configured.
"""

import copy
from typing import Any

from agents.state import AgentState
from prompts import WEATHER_ADAPT_PROMPT, fill_prompt
from services.llm import acall_llm


# Tidy: _fill_prompt removed — now imported as fill_prompt from prompts package.


def _format_weather_and_itinerary(state: AgentState) -> tuple[str, str]:
    """Extract weather data and itinerary summary from state."""
    weather = state.get("weather_data", {})
    draft = state.get("draft_itinerary", {})

    weather_lines = []
    for day_key, item in weather.items():
        weather_lines.append(
            f"  {day_key}: {item.get('condition', '?')}，"
            f"{item.get('high', '?')}°C / {item.get('low', '?')}°C，"
            f"降水概率 {item.get('precip_prob', 0):.0%}"
        )
    weather_text = "\n".join(weather_lines) if weather_lines else "暂无天气数据"

    itinerary_lines = []
    for day in draft.get("days", []):
        idx = day.get("day_index", 0)
        date_key = list(weather.keys())[idx] if idx < len(weather) else ""
        item = weather.get(date_key, {})
        itinerary_lines.append(
            f"第{idx + 1}天（{date_key}，{item.get('condition', '晴')}）："
        )
        for activity in day.get("activities", []):
            indoor_text = "室内" if activity.get("indoor_backup") else "室外"
            itinerary_lines.append(
                f"  - {activity.get('period', '')}：{activity.get('name')}"
                f"（{activity.get('type', '?')}，{indoor_text}）"
            )

    return weather_text, "\n".join(itinerary_lines)


def _is_rain(weather: dict) -> bool:
    """Return True for Chinese or English rain/snow/storm conditions."""
    condition = str(weather.get("condition", ""))
    condition_en = str(weather.get("condition_en", ""))
    text = f"{condition} {condition_en}".lower()
    return any(
        token in text
        for token in ("雨", "雪", "雷", "阵", "rain", "snow", "storm", "shower")
    )


def _is_hot(weather: dict) -> bool:
    """Return True when the daily high exceeds 35°C."""
    try:
        return float(weather.get("high", 0)) > 35
    except (TypeError, ValueError):
        return False


def _is_outdoor(activity: dict) -> bool:
    """Outdoor activities are the weather-sensitive activity types."""
    return activity.get("type") not in ("室内", "留白", "美食")


def _hour(activity: dict) -> int:
    """Parse the 24h hour from an activity start_time."""
    start = str(activity.get("start_time", ""))
    if not start:
        return 12
    try:
        return int(start.split(":")[0])
    except (TypeError, ValueError):
        return 12


def _find_indoor_replacement(act: dict, indoor_map: dict, pois: list) -> dict | None:
    """Pick an indoor alternative for the given outdoor activity."""
    if act["name"] in indoor_map:
        return indoor_map[act["name"]]

    for poi in pois:
        if poi.get("indoor") and poi.get("type") == "文化":
            return poi
    for poi in pois:
        if poi.get("indoor"):
            return poi

    return {
        "name": "室内咖啡馆",
        "type": "室内",
        "cost": 50,
        "location": "市区",
        "description": "在室内咖啡馆躲开坏天气，喝杯热饮慢慢聊天。",
    }


def _apply_replacement(
    activity: dict,
    replacement: dict,
    day_index: int,
    reason: str,
    swaps: list,
) -> None:
    """Replace an outdoor activity with an indoor one and record the swap."""
    original_name = activity.get("name", "")
    activity["name"] = replacement.get("name", activity.get("name"))
    activity["type"] = replacement.get("type", activity.get("type", "室内"))
    activity["location"] = replacement.get("location", activity.get("location", ""))
    activity["description"] = replacement.get(
        "description",
        activity.get("description", ""),
    )
    activity["estimated_cost"] = float(
        replacement.get("cost", activity.get("estimated_cost", 0))
    )
    activity["duration_min"] = int(
        replacement.get("duration_min", activity.get("duration_min", 60))
    )
    activity["indoor_backup"] = original_name
    activity["weather_note"] = reason

    swaps.append(
        {
            "day_index": day_index,
            "original_name": original_name,
            "replacement_name": activity["name"],
            "reason": reason,
            "adjustment_type": "swap",
        }
    )


def _apply_time_shift(
    activity: dict,
    day_index: int,
    reason: str,
    swaps: list,
) -> None:
    """Move a hot midday outdoor activity to a cooler period."""
    original_name = activity.get("name", "")
    hour = _hour(activity)
    target_period = "上午" if hour < 14 else "晚间"
    target_time = "08:00" if target_period == "上午" else "17:00"

    activity["period"] = target_period
    activity["start_time"] = target_time
    activity["weather_note"] = reason

    swaps.append(
        {
            "day_index": day_index,
            "original_name": original_name,
            "replacement_name": original_name,
            "reason": reason,
            "adjustment_type": "time_shift",
        }
    )


def _rule_based_adapt(state: AgentState) -> tuple[dict, list]:
    """Deterministically apply rain and high-temperature itinerary changes."""
    weather = state.get("weather_data", {})
    draft = copy.deepcopy(state.get("draft_itinerary", {}))
    pois = state.get("poi_list", [])
    swaps: list[dict] = []

    indoor_map = {poi["name"]: poi for poi in pois if poi.get("indoor")}
    date_keys = list(weather.keys())

    for day_data in draft.get("days", []):
        day_index = day_data.get("day_index", 0)
        date_key = date_keys[day_index] if day_index < len(date_keys) else ""
        item = weather.get(date_key, {})

        if not _is_rain(item) and not _is_hot(item):
            continue

        condition = item.get("condition", "")
        for activity in day_data.get("activities", []):
            if not _is_outdoor(activity):
                continue

            if _is_rain(item):
                replacement = _find_indoor_replacement(activity, indoor_map, pois)
                if replacement:
                    _apply_replacement(
                        activity,
                        replacement,
                        day_index,
                        f"{condition}，已切换室内备选",
                        swaps,
                    )
                continue

            if _is_hot(item) and 11 <= _hour(activity) <= 15:
                _apply_time_shift(
                    activity,
                    day_index,
                    f"高温{float(item.get('high', 0)):.0f}°C，避开正午户外活动",
                    swaps,
                )

    return draft, swaps


def _apply_llm_swaps(
    draft: dict,
    llm_swaps: list,
    llm_shifts: list,
) -> list:
    """Apply LLM-produced adjustments and return UI-ready swap records."""
    swaps: list[dict] = []
    days = draft.get("days", [])

    for swap in llm_swaps:
        day_index = int(swap.get("day_index", 0))
        if day_index >= len(days):
            continue

        original = swap.get("original", {}) or {}
        replacement = swap.get("replacement", {}) or {}
        original_name = original.get("name", "")

        for activity in days[day_index].get("activities", []):
            if activity.get("name") != original_name:
                continue
            _apply_replacement(
                activity,
                replacement,
                day_index,
                str(swap.get("reason", "天气调整，切换室内方案")),
                swaps,
            )
            break

    for shift in llm_shifts:
        day_index = int(shift.get("day_index", 0))
        if day_index >= len(days):
            continue

        activity_name = shift.get("activity", "")
        for activity in days[day_index].get("activities", []):
            if activity.get("name") != activity_name:
                continue
            activity["period"] = shift.get("to_period", activity.get("period"))
            activity["weather_note"] = str(shift.get("reason", "高温调整"))
            swaps.append(
                {
                    "day_index": day_index,
                    "original_name": activity_name,
                    "replacement_name": activity_name,
                    "reason": str(shift.get("reason", "高温调整")),
                    "adjustment_type": "time_shift",
                }
            )
            break

    return swaps


async def adapt_weather(state: AgentState) -> dict[str, Any]:
    """Apply weather-based adjustments to the draft itinerary.

    P0.2: converted to async for non-blocking LLM calls.
    """
    weather_text, itinerary_text = _format_weather_and_itinerary(state)

    adapt_prompt = fill_prompt(
        WEATHER_ADAPT_PROMPT,
        weather_data=weather_text,
        itinerary_summary=itinerary_text,
    )

    result = await acall_llm(
        system_prompt="你是一个细心的行程调整助手。",
        user_prompt=adapt_prompt,
        mock_response={"swaps": [], "time_shifts": [], "warnings": []},
    )

    llm_swaps = result.get("swaps", []) or []
    llm_shifts = result.get("time_shifts", []) or []

    if llm_swaps or llm_shifts:
        draft = copy.deepcopy(state.get("draft_itinerary", {}))
        weather_swaps = _apply_llm_swaps(draft, llm_swaps, llm_shifts)
    else:
        draft, weather_swaps = _rule_based_adapt(state)

    return {
        "draft_itinerary": draft,
        "weather_swaps": weather_swaps,
        "current_phase": "adapt_weather",
    }
