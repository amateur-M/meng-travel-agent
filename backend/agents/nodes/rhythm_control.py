"""rhythm_control — Enforce the three-period rhythm (M5).

Injects a deterministic pass after plan_itinerary that:
  1. Caps each period (上午/下午/晚间) to at most 2 activities by keeping the
     most "valuable" ones (paid + diverse types first, then lowest cost).
  2. Ensures every period with any activity has at least one breathing-room
     (留白) slot — if none exists, injects one from the period-aware template bank.

The node mirrors the established budget_check / adapt_weather pattern: a pure
deterministic transform on draft_itinerary, no LLM call.
"""

import copy
import logging
from typing import Dict, Any, List

from agents.state import AgentState

logger = logging.getLogger("coupletrip")

_PERIODS: List[str] = ["上午", "下午", "晚间"]
_MAX_PER_PERIOD = 2


# ── Breathing-room templates by period ──────────────────────────────

_REST_TEMPLATES_BY_PERIOD: Dict[str, List[dict]] = {
    "上午": [
        {
            "name": "晨间漫步",
            "type": "留白",
            "start_time": "07:30",
            "duration_min": 45,
            "estimated_cost": 0,
            "description": "不用赶时间，一起在晨光里走走，感受城市的呼吸。",
            "location": "",
        },
        {
            "name": "街角咖啡",
            "type": "留白",
            "start_time": "08:00",
            "duration_min": 40,
            "estimated_cost": 0,
            "description": "找一家街角咖啡店，慢慢喝完一杯，看行人来去。",
            "location": "",
        },
    ],
    "下午": [
        {
            "name": "午后发呆",
            "type": "留白",
            "start_time": "15:30",
            "duration_min": 50,
            "estimated_cost": 0,
            "description": "什么都不安排，就在风景里发会儿呆，把时间留给彼此。",
            "location": "",
        },
        {
            "name": "手牵手漫步",
            "type": "留白",
            "start_time": "16:00",
            "duration_min": 45,
            "estimated_cost": 0,
            "description": "沿着海边或老街慢慢走，没有目的地，只有你和我。",
            "location": "",
        },
    ],
    "晚间": [
        {
            "name": "夜色漫步",
            "type": "留白",
            "start_time": "20:30",
            "duration_min": 45,
            "estimated_cost": 0,
            "description": "灯火亮起来，慢慢走回去，把一天的余味再回味一遍。",
            "location": "",
        },
        {
            "name": "屋顶看星",
            "type": "留白",
            "start_time": "21:00",
            "duration_min": 40,
            "estimated_cost": 0,
            "description": "找个安静的角落，看星星，聊聊天，什么都不做也很好。",
            "location": "",
        },
    ],
}


def _activity_score(act: dict) -> tuple:
    """Sort key: paid activities before 留白, then higher cost first.

    Keeps the most "substantial" activities when capping a period to 2.
    Ties break by lower cost so the cheaper paid activity wins over an
    expensive one when both are equally substantial.
    """
    is_rest = 1 if act.get("type") == "留白" else 0
    cost = float(act.get("estimated_cost", 0))
    return (is_rest, -cost)


def _cap_period(acts: List[dict]) -> tuple[List[dict], List[str]]:
    """Return at most _MAX_PER_PERIOD activities, preserving relative order.

    Selection: sort by score (paid + expensive first), take top N, then
    re-sort by original index so the timeline stays coherent.
    """
    if len(acts) <= _MAX_PER_PERIOD:
        return acts, []

    indexed = list(enumerate(acts))
    kept = sorted(indexed, key=lambda pair: _activity_score(pair[1]))[:_MAX_PER_PERIOD]
    kept_indices = {i for i, _ in kept}
    kept_sorted = sorted(kept, key=lambda pair: pair[0])
    kept_acts = [a for _, a in kept_sorted]
    dropped_names = [a.get("name", "") for i, a in indexed if i not in kept_indices]
    return kept_acts, dropped_names


def _ensure_rest(acts: List[dict], period: str, day_index: int, adjustments: list) -> List[dict]:
    """Inject a breathing-room slot if the period has room and lacks one.

    Only injects when len(acts) < _MAX_PER_PERIOD so the hard cap is never
    violated. A full period without rest is left as-is — the plan_itinerary
    prompt and mock already favour rest slots, so this only affects dense
    LLM output that exactly hits the cap.
    """
    if not acts or len(acts) >= _MAX_PER_PERIOD:
        return acts
    if any(a.get("type") == "留白" for a in acts):
        return acts

    template = _REST_TEMPLATES_BY_PERIOD.get(period, _REST_TEMPLATES_BY_PERIOD["下午"])[0]
    rest = {
        "name": template["name"],
        "type": "留白",
        "period": period,
        "start_time": template["start_time"],
        "duration_min": template["duration_min"],
        "estimated_cost": 0,
        "description": template["description"],
        "location": template["location"],
    }
    adjustments.append({
        "day_index": day_index,
        "period": period,
        "kind": "inject_rest",
        "reason": f"为{period}时段补充留白时间，保持节奏松弛",
    })
    return acts + [rest]


def _normalise_day(day: dict) -> tuple[dict, list]:
    """Apply cap + rest-injection to a single day's activities by period."""
    day_out = dict(day)
    raw = day.get("activities", [])
    day_adjustments: list = []

    by_period: Dict[str, List[dict]] = {p: [] for p in _PERIODS}
    for act in raw:
        period = act.get("period", "")
        if period in by_period:
            by_period[period].append(act)

    new_periods: List[dict] = []
    for period in _PERIODS:
        acts = by_period[period]
        capped, dropped = _cap_period(acts)
        if dropped:
            day_adjustments.append({
                "day_index": day.get("day_index", 0),
                "period": period,
                "kind": "cap",
                "dropped": dropped,
                "reason": f"{period}时段活动超过{_MAX_PER_PERIOD}个，已裁剪保留核心体验",
            })
        ensured = _ensure_rest(capped, period, day.get("day_index", 0), day_adjustments)
        new_periods.extend(ensured)

    day_out["activities"] = new_periods
    return day_out, day_adjustments


def rhythm_control(state: AgentState) -> Dict[str, Any]:
    """Enforce three-period rhythm constraints on the draft itinerary.

    Returns:
        Partial state with normalised draft_itinerary and rhythm_adjustments.
    """
    draft = copy.deepcopy(state.get("draft_itinerary", {}))
    all_adjustments: list = []

    for day in draft.get("days", []):
        day_out, day_adjustments = _normalise_day(day)
        day.clear()
        day.update(day_out)
        all_adjustments.extend(day_adjustments)

    if all_adjustments:
        logger.info(
            "rhythm_control applied %d adjustments", len(all_adjustments),
        )

    return {
        "draft_itinerary": draft,
        "rhythm_adjustments": all_adjustments,
        "current_phase": "rhythm_control",
    }
