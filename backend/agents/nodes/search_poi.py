"""search_poi — Search for attractions / points-of-interest near destination.

M2: delegates to poi_search_tool with a rich 5-city mock database.
API interface (Amap / Google Maps Places) reserved for M2+.
"""

import json
from typing import Dict, Any, List

from agents.state import AgentState
from tools.poi_search_tool import poi_search_tool


def search_poi(state: AgentState) -> Dict[str, Any]:
    """Search attractions for the given destination via poi_search_tool.

    The tool returns a JSON array of POI dicts with name, type, rating,
    cost, location, indoor flag, and couple_score.  Preferences are passed
    as comma-separated tags for filtering.

    Returns:
        Partial state with poi_list populated.
    """
    params = state.get("parsed_params", {})
    destination = params.get("destination", "")
    preferences = params.get("preferences", [])

    # Build preference string for the tool
    pref_str = ",".join(preferences) if preferences else ""

    try:
        result = poi_search_tool.invoke({
            "city": destination,
            "preferences": pref_str,
        })
        candidates = json.loads(result)
    except Exception:
        # Fallback: minimal generic list
        candidates = [
            {"name": f"{destination}城市公园", "type": "自然", "rating": 4.0,
             "cost": 0, "location": f"{destination}市区", "indoor": False},
            {"name": f"{destination}博物馆", "type": "文化", "rating": 4.0,
             "cost": 0, "location": f"{destination}市区", "indoor": True},
        ]

    return {
        "poi_list": candidates,
        "current_phase": "search_poi",
    }
