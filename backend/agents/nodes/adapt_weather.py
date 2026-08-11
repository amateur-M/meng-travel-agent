"""adapt_weather — Adjust itinerary for rain or extreme heat.

Reads weather_data and draft_itinerary; swaps outdoor → indoor activities
when conditions are unfavourable.
"""

from typing import Dict, Any

from agents.state import AgentState


def adapt_weather(state: AgentState) -> Dict[str, Any]:
    """Apply weather-based adjustments to the draft itinerary.

    Logic (M1 rule-based, no LLM call):
      - 中雨/大雨/暴雨 → outdoor activities → indoor from poi_list
      - > 35°C          → move 11:00-15:00 outdoor to morning or evening

    Returns:
        Partial state with draft_itinerary optionally modified.
    """
    weather = state.get("weather_data", {})
    draft = state.get("draft_itinerary", {})
    pois = state.get("poi_list", [])

    # map poi name → indoor backup
    indoor_map = {p["name"]: p for p in pois if p.get("indoor")}

    swaps: list[dict] = []
    modified = False

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

            # ── rain → indoor swap ────────────────────────────────
            if is_rain and act.get("type") not in ("室内", "留白", "美食"):
                replacement = _find_indoor_replacement(act, indoor_map, pois)
                if replacement:
                    swaps.append({
                        "day": day_idx,
                        "period": act.get("period", ""),
                        "original": act["name"],
                        "replacement": replacement["name"],
                        "reason": f"{condition}，切换室内方案",
                    })
                    act["name"] = replacement["name"]
                    act["type"] = replacement.get("type", "室内")
                    act["location"] = replacement.get("location", "")
                    act["indoor_backup"] = act.get("name", "")
                    modified = True

            # ── heat → reschedule ─────────────────────────────────
            elif is_hot and 11 <= hour <= 15 and act.get("type") not in ("室内", "留白", "美食"):
                act["start_time"] = "08:00" if hour < 13 else "17:00"
                act["weather_note"] = "高温调整：避开正午时段"
                modified = True

    return {
        "draft_itinerary": draft,
        "current_phase": "adapt_weather",
    }


def _find_indoor_replacement(act: dict, indoor_map: dict, pois: list) -> dict | None:
    """Pick an indoor alternative for the given outdoor activity."""
    # first: try exact name match in indoor_map
    if act["name"] in indoor_map:
        return indoor_map[act["name"]]

    # second: pick any indoor POI not yet used as replacement
    for p in pois:
        if p.get("indoor"):
            # prefer culture type
            if p.get("type") in ("文化",):
                return p

    # third: just grab the first indoor
    for p in pois:
        if p.get("indoor"):
            return p

    # fallback: generic indoor
    return {"name": "室内咖啡馆", "type": "室内", "cost": 50, "location": "市区"}
