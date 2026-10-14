"""budget_check — Validate draft itinerary against budget and generate downgrades.

M4: applies a deterministic in-place downgrade when over budget.
P6: removed retry_count mechanism and BUDGET_CHECK_PROMPT import — the
conditional retry loop in graph.py was unreachable dead code after M4.
"""

import copy
from typing import Dict, Any

from agents.state import AgentState
from prompts import BUDGET_DOWNGRADE_PROMPT, fill_prompt
from services.llm import acall_llm


def _sum_costs(draft: dict) -> float:
    total = 0.0
    for day in draft.get("days", []):
        for act in day.get("activities", []):
            total += float(act.get("estimated_cost", 0))
    return total


def _daily_costs(draft: dict) -> list:
    return [
        sum(float(a.get("estimated_cost", 0)) for a in d.get("activities", []))
        for d in draft.get("days", [])
    ]


def _warning_level(total_spent: float, budget: float) -> str:
    """Map budget usage to a UI warning level."""
    if budget <= 0:
        return "over"
    ratio = total_spent / budget
    if ratio > 1:
        return "over"
    if ratio >= 0.9:
        return "warning"
    return "ok"


def _replacement_cost(activity: dict, replacement: dict) -> float:
    """Resolve a replacement POI/restaurant dict to an activity cost."""
    if activity.get("type") == "美食":
        return float(replacement.get("avg_cost", replacement.get("cost", 0))) * 2
    return float(replacement.get("cost", replacement.get("avg_cost", 0)))


def _candidate_replacement(activity: dict, state: AgentState) -> dict:
    """Pick a cheaper alternative from POI/food candidates, or a safe free option."""
    pool = state.get("food_list", []) if activity.get("type") == "美食" else state.get("poi_list", [])
    current_cost = float(activity.get("estimated_cost", 0))

    for candidate in sorted(pool, key=lambda item: float(item.get("cost", item.get("avg_cost", 0)))):
        if _replacement_cost(activity, candidate) < current_cost:
            return candidate

    if activity.get("type") == "美食":
        return {
            "name": "街边小吃",
            "type": "美食",
            "avg_cost": 15,
            "location": "市区",
            "description": "换成轻松实惠的街边小吃，省下预算也很有烟火气。",
        }
    return {
        "name": "城市漫步",
        "type": "留白",
        "cost": 0,
        "location": "市区",
        "description": "改成一段不花钱的城市漫步，把时间留给彼此。",
    }


def _apply_budget_adjustments(draft: dict, adjustments: list) -> list:
    """Apply structured LLM/rule adjustments to the itinerary in place."""
    applied = []
    days = draft.get("days", [])

    for adjustment in adjustments:
        day_index = int(adjustment.get("day_index", 0))
        if day_index >= len(days):
            continue

        original = adjustment.get("original", {}) or {}
        replacement = adjustment.get("replacement", {}) or {}
        original_name = original.get("name", "")
        if not original_name:
            continue

        for activity in days[day_index].get("activities", []):
            if activity.get("name") == original_name:
                activity["name"] = replacement.get("name", activity.get("name"))
                activity["type"] = replacement.get("type", activity.get("type"))
                activity["location"] = replacement.get("location", activity.get("location", ""))
                activity["description"] = replacement.get(
                    "description",
                    activity.get("description", ""),
                )
                activity["estimated_cost"] = float(
                    replacement.get(
                        "estimated_cost",
                        replacement.get("cost", activity.get("estimated_cost", 0)),
                    )
                )
                applied.append(adjustment)
                break

    return applied


def _rule_based_budget_downgrade(
    state: AgentState,
    draft: dict,
    budget: float,
) -> tuple[dict, list]:
    """Deterministically replace expensive items until the plan fits the budget."""
    adjusted_draft = copy.deepcopy(draft)
    adjustments = []
    total_spent = _sum_costs(adjusted_draft)

    changed = True
    while total_spent > budget and changed:
        changed = False

        for day in adjusted_draft.get("days", []):
            if total_spent <= budget:
                break

            day_index = day.get("day_index", 0)
            paid = [
                activity
                for activity in day.get("activities", [])
                if float(activity.get("estimated_cost", 0)) > 0
            ]

            for activity in sorted(
                paid,
                key=lambda item: float(item.get("estimated_cost", 0)),
                reverse=True,
            ):
                if total_spent <= budget:
                    break

                original_cost = float(activity.get("estimated_cost", 0))
                replacement = _candidate_replacement(activity, state)
                new_cost = _replacement_cost(activity, replacement)

                if new_cost >= original_cost:
                    new_cost = 0
                    replacement = {
                        "name": "免费体验",
                        "type": "留白",
                        "cost": 0,
                        "location": "市区",
                        "description": "用免费体验替代原付费项目，省下预算不减浪漫。",
                    }

                adjustments.append(
                    {
                        "day_index": day_index,
                        "original": {
                            "name": activity.get("name"),
                            "cost": original_cost,
                        },
                        "replacement": {
                            "name": replacement.get("name"),
                            "type": replacement.get("type", activity.get("type")),
                            "estimated_cost": new_cost,
                            "description": replacement.get("description", ""),
                            "location": replacement.get("location", ""),
                        },
                        "saving": round(original_cost - new_cost, 2),
                        "reason": f"将「{activity.get('name')}」替换为更省预算的「{replacement.get('name')}」",
                        "impact": "低",
                    }
                )

                activity["name"] = replacement.get("name", activity.get("name"))
                activity["type"] = replacement.get("type", activity.get("type"))
                activity["location"] = replacement.get("location", activity.get("location", ""))
                activity["description"] = replacement.get(
                    "description",
                    activity.get("description", ""),
                )
                activity["estimated_cost"] = new_cost
                total_spent -= original_cost - new_cost
                changed = True

    return adjusted_draft, adjustments


def _format_itinerary_summary(draft: dict) -> str:
    lines = []
    for day in draft.get("days", []):
        day_idx = day.get("day_index", 0) + 1
        daily = sum(float(a.get("estimated_cost", 0)) for a in day.get("activities", []))
        lines.append(f"Day {day_idx} (spent {daily:.0f}):")
        for act in day.get("activities", []):
            lines.append(f"  - {act['name']}: {act.get('estimated_cost', 0):.0f}")
    return "\n".join(lines)


# Tidy: _fill_prompt removed — now imported as fill_prompt from prompts package.


async def budget_check(state: AgentState) -> Dict[str, Any]:
    """Audit the draft itinerary's spending against the total budget.

    P6: retry_count removed — the conditional retry loop in graph.py was
    unreachable after M4 made budget_check always apply a deterministic
    in-place downgrade.  The node now simply downgrades and moves on.
    P0.2: converted to async for non-blocking LLM calls.
    """
    params = state.get("parsed_params", {})
    draft = state.get("draft_itinerary", {})
    budget = params.get("budget", 3000)
    total_spent = _sum_costs(draft)
    original_spent = total_spent

    downgrade_notes: list = []
    downgrade_suggestions: list = []
    downgrade_applied = False

    if total_spent > budget:
        summary = _format_itinerary_summary(draft)
        over_amount = original_spent - budget
        fallback_draft, fallback_adjustments = _rule_based_budget_downgrade(
            state,
            draft,
            budget,
        )

        downgrade_prompt = fill_prompt(
            BUDGET_DOWNGRADE_PROMPT,
            budget=budget,
            current_spent=original_spent,
            over_budget="true",
            over_amount=round(over_amount, 0),
            itinerary_summary=summary,
        )

        result = await acall_llm(
            system_prompt="You are a travel budget advisor.",
            user_prompt=downgrade_prompt,
            mock_response={
                "adjusted": True,
                "original_total": original_spent,
                "adjusted_total": _sum_costs(fallback_draft),
                "savings": round(original_spent - _sum_costs(fallback_draft), 2),
                "adjustments": fallback_adjustments,
                "summary": f"已生成降级方案，将总花费从 {original_spent:.0f} 元压到 {_sum_costs(fallback_draft):.0f} 元，尽量保留最值得体验的部分。",
            },
        )

        adjustments = result.get("adjustments", []) or []
        if result.get("adjusted") and adjustments:
            downgrade_suggestions = _apply_budget_adjustments(draft, adjustments)

        # If the LLM did not provide a usable adjustment list, use the
        # deterministic fallback. Also fall back if the LLM's edits still
        # leave the plan over budget.
        if not downgrade_suggestions or _sum_costs(draft) > budget:
            draft = fallback_draft
            downgrade_suggestions = fallback_adjustments

        downgrade_applied = bool(downgrade_suggestions)
        if downgrade_suggestions:
            downgrade_notes = [
                str(item.get("reason", ""))
                for item in downgrade_suggestions
                if item.get("reason")
            ]
            summary = str(result.get("summary", "") or "")
            if summary:
                downgrade_notes.append(summary)
        else:
            downgrade_notes.append(
                f"Total {original_spent:.0f} exceeds budget {budget:.0f}. Replace expensive items."
            )

        total_spent = _sum_costs(draft)

    daily = _daily_costs(draft)
    over = total_spent > budget
    ratio = total_spent / budget if budget > 0 else 0.0

    # P6: retry_count removed — the conditional retry loop was dead code.
    return {
        "draft_itinerary": draft,
        "budget_breakdown": {
            "total_budget": budget,
            "total_spent": total_spent,
            "over_budget": over,
            "by_day": daily,
            "warning_level": _warning_level(total_spent, budget),
            "spending_ratio": round(ratio, 4),
            "downgrade_applied": downgrade_applied or original_spent > budget,
            "downgrade_notes": downgrade_notes,
        },
        "downgrade_suggestions": downgrade_suggestions,
        "current_phase": "budget_check",
    }
