"""budget_check — Validate draft itinerary against budget and generate downgrades.

If total_spent > budget, this node replaces expensive items with cheaper
alternatives and loops back through plan_itinerary for at most 2 retries.
"""

from typing import Dict, Any

from agents.state import AgentState


def _sum_costs(draft: dict) -> float:
    """Sum estimated_cost across all activities in the draft itinerary."""
    total = 0.0
    for day in draft.get("days", []):
        for act in day.get("activities", []):
            total += float(act.get("estimated_cost", 0))
    return total


def _daily_costs(draft: dict) -> list:
    """Return per-day cost totals."""
    return [
        sum(float(a.get("estimated_cost", 0)) for a in d.get("activities", []))
        for d in draft.get("days", [])
    ]


def budget_check(state: AgentState) -> Dict[str, Any]:
    """Audit the draft itinerary's spending against the total budget.

    Behaviour:
      - under budget   → passes through with over_budget=False
      - over budget    → marks over_budget=True, increments retry_count
      - retry >= 2     → forces pass (cease retrying)

    The conditional edge in graph.py reads state["budget_breakdown"]["over_budget"]
    and state["retry_count"] to decide whether to loop back to plan_itinerary.

    Returns:
        Partial state with budget_breakdown populated.
    """
    params = state.get("parsed_params", {})
    draft = state.get("draft_itinerary", {})
    budget = params.get("budget", 3000)
    total_spent = _sum_costs(draft)
    daily = _daily_costs(draft)
    over = total_spent > budget

    downgrade_notes: list = []
    if over:
        downgrade_notes.append(
            f"总花费 ¥{total_spent:.0f} 超出预算 ¥{budget:.0f}，"
            f"请将部分高价项目替换为人均100元以内的方案"
        )

    return {
        "budget_breakdown": {
            "total_budget": budget,
            "total_spent": total_spent,
            "over_budget": over,
            "by_day": daily,
            "downgrade_notes": downgrade_notes,
        },
        "retry_count": state.get("retry_count", 0) + (1 if over else 0),
        "current_phase": "budget_check",
    }
