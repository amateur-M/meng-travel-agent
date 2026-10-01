"""search_food — Search for restaurants near destination."""

import json
import logging
from typing import Dict, Any

from agents.state import AgentState
from tools.food_search_tool import food_search_tool

logger = logging.getLogger("coupletrip")


def search_food(state: AgentState) -> Dict[str, Any]:
    """Search restaurants for the destination via the live Amap food tool.

    P2: on failure, append a warning instead of setting `error` so the
    pipeline can continue with an empty candidate list (graceful degradation).
    """
    params = state.get("parsed_params", {})
    destination = params.get("destination", "")
    budget = params.get("budget", 3000)
    num_days = params.get("num_days", 2)
    daily_budget = budget / max(num_days, 1)

    warnings: list = []
    try:
        result = food_search_tool.invoke({
            "city": destination,
            "cuisine": "不限",
            "budget_per_person": daily_budget / 2,
        })
        candidates = json.loads(result)
    except Exception as exc:
        candidates = []
        warnings.append(f"美食搜索失败，已降级处理: {exc}")
        # P10: log the degradation
        logger.warning("Food search failed for %s: %s", destination, exc, exc_info=True)

    return {
        "food_list": candidates,
        "warnings": warnings,
        "current_phase": "search_food",
    }
