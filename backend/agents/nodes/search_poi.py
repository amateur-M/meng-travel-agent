"""search_poi — Search for attractions / points-of-interest near destination."""

import json
from typing import Dict, Any

from agents.state import AgentState
from tools.poi_search_tool import poi_search_tool


def search_poi(state: AgentState) -> Dict[str, Any]:
    """Search attractions for the destination via the live Amap POI tool."""
    params = state.get("parsed_params", {})
    destination = params.get("destination", "")
    preferences = params.get("preferences", [])
    pref_str = ",".join(preferences) if preferences else ""

    try:
        result = poi_search_tool.invoke({
            "city": destination,
            "preferences": pref_str,
        })
        candidates = json.loads(result)
        error = ""
    except Exception as exc:
        candidates = []
        error = f"景点搜索失败: {exc}"

    return {
        "poi_list": candidates,
        "error": error,
        "current_phase": "search_poi",
    }
