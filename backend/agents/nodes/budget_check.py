"""budget_check — Validate draft itinerary against budget and generate downgrades.

M2: when over budget, calls LLM via services.llm with the
BUDGET_DOWNGRADE_PROMPT to generate smart downgrade suggestions.
Falls back to simple note-based downgrade when API key is absent.
"""

import json
from typing import Dict, Any

from agents.state import AgentState
from prompts import BUDGET_CHECK_PROMPT, BUDGET_DOWNGRADE_PROMPT
from services.llm import call_llm


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


def _format_itinerary_summary(draft: dict) -> str:
    lines = []
    for day in draft.get("days", []):
        day_idx = day.get("day_index", 0) + 1
        daily = sum(float(a.get("estimated_cost", 0)) for a in day.get("activities", []))
        lines.append(f"Day {day_idx} (spent {daily:.0f}):")
        for act in day.get("activities", []):
            lines.append(f"  - {act['name']}: {act.get('estimated_cost', 0):.0f}")
    return "\n".join(lines)


def _fill_prompt(template: str, **kwargs) -> str:
    """Fill template placeholders using str.replace to avoid JSON brace conflicts."""
    result = template
    for key, val in kwargs.items():
        result = result.replace("{" + key + "}", str(val))
    return result


def budget_check(state: AgentState) -> Dict[str, Any]:
    """Audit the draft itinerary's spending against the total budget."""
    params = state.get("parsed_params", {})
    draft = state.get("draft_itinerary", {})
    budget = params.get("budget", 3000)
    total_spent = _sum_costs(draft)
    daily = _daily_costs(draft)
    over = total_spent > budget
    retry_count = state.get("retry_count", 0)

    downgrade_notes: list = []

    if over and retry_count < 2:
        summary = _format_itinerary_summary(draft)
        over_amount = total_spent - budget

        downgrade_prompt = _fill_prompt(
            BUDGET_DOWNGRADE_PROMPT,
            budget=budget,
            current_spent=total_spent,
            over_budget="true",
            over_amount=round(over_amount, 0),
            itinerary_summary=summary,
        )

        result = call_llm(
            system_prompt="You are a travel budget advisor.",
            user_prompt=downgrade_prompt,
            mock_response={
                "adjusted": True,
                "original_total": total_spent,
                "adjusted_total": budget,
                "savings": over_amount,
                "adjustments": [],
                "summary": f"Total {total_spent:.0f} exceeds budget {budget:.0f}. Replace expensive items.",
            },
        )

        if result.get("adjusted"):
            downgrade_notes = [adj.get("reason", "") for adj in result.get("adjustments", [])]
            downgrade_notes.append(result.get("summary", ""))
            if "downgrade_suggestions" not in state:
                state["downgrade_suggestions"] = []
            state["downgrade_suggestions"] = result.get("adjustments", [])
        else:
            downgrade_notes.append(
                f"Total {total_spent:.0f} exceeds budget {budget:.0f}. Replace expensive items."
            )

    return {
        "budget_breakdown": {
            "total_budget": budget,
            "total_spent": total_spent,
            "over_budget": over,
            "by_day": daily,
            "downgrade_notes": downgrade_notes,
        },
        "retry_count": retry_count + (1 if over else 0),
        "current_phase": "budget_check",
    }
