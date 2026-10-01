"""search_poi — Search for attractions / points-of-interest near destination."""

import json
import logging
from typing import Dict, Any

from agents.state import AgentState
from tools.poi_search_tool import poi_search_tool

logger = logging.getLogger("coupletrip")


def search_poi(state: AgentState) -> Dict[str, Any]:
    """Search attractions for the destination via the live Amap POI tool.

    P2: on failure, append a warning instead of setting `error` so the
    pipeline can continue with an empty candidate list (graceful degradation).
    """
    params = state.get("parsed_params", {})
    destination = params.get("destination", "")
    preferences = params.get("preferences", [])
    pref_str = ",".join(preferences) if preferences else ""

    warnings: list = []
    try:
        result = poi_search_tool.invoke({
            "city": destination,
            "preferences": pref_str,
        })
        candidates = json.loads(result)
    except Exception as exc:
        candidates = []
        warnings.append(f"景点搜索失败，已降级处理: {exc}")
        # P10: log the degradation
        logger.warning("POI search failed for %s: %s", destination, exc, exc_info=True)

    return {
        "poi_list": candidates,
        "warnings": warnings,
        "current_phase": "search_poi",
    }
