"""search_food — Search for restaurants near destination."""

import json
from typing import Dict, Any

from agents.state import AgentState
from tools.food_search_tool import food_search_tool


def search_food(state: AgentState) -> Dict[str, Any]:
    """Search restaurants for the destination via the live Amap food tool."""
    params = state.get("parsed_params", {})
    destination = params.get("destination", "")
    budget = params.get("budget", 3000)
    num_days = params.get("num_days", 2)
    daily_budget = budget / max(num_days, 1)

    try:
        result = food_search_tool.invoke({
            "city": destination,
            "cuisine": "不限",
            "budget_per_person": daily_budget / 2,
        })
        candidates = json.loads(result)
        error = ""
    except Exception as exc:
        candidates = []
        error = f"美食搜索失败: {exc}"

    return {
        "food_list": candidates,
        "error": error,
        "current_phase": "search_food",
    }
