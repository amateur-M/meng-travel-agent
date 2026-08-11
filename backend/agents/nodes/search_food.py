"""search_food — Search for restaurants near destination.

M2: delegates to food_search_tool with a rich 5-city mock database.
API interface (Amap / Google Places) reserved for M2+.
"""

import json
from typing import Dict, Any

from agents.state import AgentState
from tools.food_search_tool import food_search_tool


def search_food(state: AgentState) -> Dict[str, Any]:
    """Search restaurants for the given destination via food_search_tool.

    The tool returns a JSON array of restaurant dicts with name, cuisine,
    avg_cost, atmosphere tags, rating, and couple_score.

    Returns:
        Partial state with food_list populated.
    """
    params = state.get("parsed_params", {})
    destination = params.get("destination", "")
    budget = params.get("budget", 3000)
    num_days = params.get("num_days", 2)
    daily_budget = budget / max(num_days, 1)

    try:
        result = food_search_tool.invoke({
            "city": destination,
            "cuisine": "不限",
            "budget_per_person": daily_budget / 2,  # per-person rough estimate
        })
        candidates = json.loads(result)
    except Exception:
        candidates = [
            {"name": f"{destination}本地餐厅", "cuisine": "本地菜", "rating": 4.0,
             "avg_cost": 60, "location": f"{destination}市区"},
            {"name": f"{destination}小吃街", "cuisine": "小吃", "rating": 4.0,
             "avg_cost": 25, "location": f"{destination}市区"},
        ]

    return {
        "food_list": candidates,
        "current_phase": "search_food",
    }
