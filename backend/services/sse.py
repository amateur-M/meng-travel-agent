"""SSE framing helpers (V4/P1: extracted from main.py).

Turning a LangGraph node update into the wire frames the frontend consumes is
a transport concern, so it lives here rather than in the HTTP entry point.
The names keep their leading underscore to match the call sites and tests that
were written against the original ``main`` module.
"""

import json


def _sse(event: str, data: dict) -> str:
    """Format a single SSE event frame."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _phase_message(phase: str) -> str:
    """Map internal phase name to a human-readable progress message."""
    messages = {
        "parse_input": "正在解析您的旅行需求...",
        "fetch_weather": "正在查询目的地天气...",
        "search_poi": "正在搜索热门景点...",
        "search_food": "正在搜索本地美食...",
        "plan_itinerary": "正在为您生成行程...",
        "rhythm_control": "正在调整行程节奏...",
        "budget_check": "正在核算预算...",
        "adapt_weather": "正在根据天气调整行程...",
        "add_couple_touch": "正在添加浪漫寄语...",
        "output_format": "正在整理最终行程...",
    }
    return messages.get(phase, f"处理中: {phase}")


def _emit_node_events(phase: str, update: dict) -> list[str]:
    """Given a node's partial state update, emit targeted SSE events.

    Besides the universal `step` event, certain nodes produce richer
    payload events (partial / budget_alert / weather_swap / message)
    that let the frontend render progressively.
    """
    events: list[str] = []

    # ── step event (always) ──────────────────────────────────────
    events.append(_sse("step", {
        "phase": phase,
        "message": _phase_message(phase),
    }))

    if phase == "plan_itinerary" or phase == "rhythm_control":
        draft = update.get("draft_itinerary", {})
        for day in draft.get("days", []):
            day_index = day.get("day_index", 0)
            events.append(_sse("partial", {
                "day_index": day_index,
                "period": "all",
                "activities": day.get("activities", []),
                "weather": day.get("weather", day.get("weather_condition", "")),
            }))

    elif phase == "budget_check":
        budget = update.get("budget_breakdown", {})
        if budget:
            events.append(_sse("budget_alert", {
                "current": budget.get("total_spent", 0),
                "limit": budget.get("total_budget", 0),
                "warning_level": budget.get("warning_level", "ok"),
                "spending_ratio": budget.get("spending_ratio", 0),
                "downgrade_applied": budget.get("downgrade_applied", False),
                "suggestions": update.get("downgrade_suggestions", []),
                "downgrade_notes": budget.get("downgrade_notes", []),
            }))

    elif phase == "adapt_weather":
        swaps = update.get("weather_swaps", [])
        for swap in swaps:
            events.append(_sse("weather_swap", {
                "day_index": swap.get("day_index", 0),
                "original": swap.get("original_name", ""),
                "replacement": swap.get("replacement_name", ""),
                "reason": swap.get("reason", ""),
                "adjustment_type": swap.get("adjustment_type", "swap"),
            }))

    elif phase == "add_couple_touch":
        draft = update.get("draft_itinerary", {})
        for day in draft.get("days", []):
            day_index = day.get("day_index", 0)
            for act in day.get("activities", []):
                note = act.get("couple_note", "")
                if note:
                    events.append(_sse("message", {
                        "day": day_index,
                        "activity": act.get("name", ""),
                        "text": note,
                    }))

    return events
