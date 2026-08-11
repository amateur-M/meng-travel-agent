"""search_poi — Search for attractions / points-of-interest near destination.

M1 placeholder: returns a curated mock POI list.
M2 will replace this with a real map API (高德 / Google Maps).
"""

from typing import Dict, Any, List

from agents.state import AgentState


# ── Destination mock POI maps ────────────────────────────────────

_MOCK_POI: Dict[str, List[dict]] = {
    "大理": [
        {"name": "洱海", "type": "自然", "rating": 4.8, "cost": 0,
         "location": "大理市洱海", "indoor": False},
        {"name": "苍山", "type": "自然", "rating": 4.7, "cost": 40,
         "location": "大理市苍山景区", "indoor": False},
        {"name": "大理古城", "type": "人文", "rating": 4.6, "cost": 0,
         "location": "大理古城", "indoor": False},
        {"name": "崇圣寺三塔", "type": "文化", "rating": 4.5, "cost": 75,
         "location": "大理市崇圣寺", "indoor": False},
        {"name": "喜洲古镇", "type": "人文", "rating": 4.4, "cost": 0,
         "location": "喜洲镇", "indoor": False},
        {"name": "双廊古镇", "type": "人文", "rating": 4.3, "cost": 0,
         "location": "双廊镇", "indoor": False},
        {"name": "大理市博物馆", "type": "文化", "rating": 4.2, "cost": 0,
         "location": "大理古城内", "indoor": True},
        {"name": "床单厂艺术区", "type": "文化", "rating": 4.1, "cost": 0,
         "location": "大理古城", "indoor": True},
        {"name": "周城扎染博物馆", "type": "文化", "rating": 4.3, "cost": 30,
         "location": "周城村", "indoor": True},
    ],
    "丽江": [
        {"name": "丽江古城", "type": "人文", "rating": 4.7, "cost": 0,
         "location": "丽江古城", "indoor": False},
        {"name": "玉龙雪山", "type": "自然", "rating": 4.8, "cost": 100,
         "location": "玉龙县", "indoor": False},
        {"name": "束河古镇", "type": "人文", "rating": 4.5, "cost": 0,
         "location": "束河镇", "indoor": False},
        {"name": "泸沽湖", "type": "自然", "rating": 4.6, "cost": 70,
         "location": "宁蒗县", "indoor": False},
        {"name": "木府", "type": "文化", "rating": 4.4, "cost": 60,
         "location": "丽江古城内", "indoor": True},
        {"name": "白沙壁画", "type": "文化", "rating": 4.2, "cost": 30,
         "location": "白沙镇", "indoor": True},
    ],
    "三亚": [
        {"name": "亚龙湾", "type": "自然", "rating": 4.8, "cost": 0,
         "location": "亚龙湾", "indoor": False},
        {"name": "蜈支洲岛", "type": "自然", "rating": 4.7, "cost": 144,
         "location": "蜈支洲岛", "indoor": False},
        {"name": "天涯海角", "type": "自然", "rating": 4.5, "cost": 81,
         "location": "天涯区", "indoor": False},
        {"name": "南山文化旅游区", "type": "文化", "rating": 4.6, "cost": 129,
         "location": "南山", "indoor": False},
        {"name": "三亚千古情", "type": "文化", "rating": 4.4, "cost": 280,
         "location": "迎宾路", "indoor": True},
        {"name": "三亚市博物馆", "type": "文化", "rating": 4.0, "cost": 0,
         "location": "三亚市区", "indoor": True},
    ],
}


def search_poi(state: AgentState) -> Dict[str, Any]:
    """Search attractions for the given destination.

    M1: returns pre-curated mock data.
    M2: replaces with live map API + LLM filtering by preferences.

    Returns:
        Partial state with poi_list populated.
    """
    params = state.get("parsed_params", {})
    destination = params.get("destination", "")
    preferences = params.get("preferences", [])

    # ── find best match ──────────────────────────────────────────
    candidates = []
    for key, pois in _MOCK_POI.items():
        if key in destination or destination in key:
            candidates = pois
            break

    if not candidates:
        # fallback: return generic list
        candidates = [
            {"name": f"{destination}推荐景点", "type": "自然", "rating": 4.5,
             "cost": 0, "location": f"{destination}市区", "indoor": False},
            {"name": f"{destination}博物馆", "type": "文化", "rating": 4.2,
             "cost": 0, "location": f"{destination}市区", "indoor": True},
        ]

    # ── optionally filter by preference ──────────────────────────
    if "文化" in preferences:
        candidates = [p for p in candidates if p["type"] in ("文化", "人文", "自然")]
    if "户外" in preferences:
        candidates = [p for p in candidates if not p.get("indoor")]

    return {
        "poi_list": candidates,
        "current_phase": "search_poi",
    }
