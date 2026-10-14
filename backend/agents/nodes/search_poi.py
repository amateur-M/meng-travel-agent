"""search_poi — Search for attractions / points-of-interest near destination.

P2.2: checks curated_pois.json first (city + preferences filter),
then supplements with live Amap results. Curated items get source='curated'
so the UI can show a '精选' badge.
"""

import json
import logging
import os
from typing import Dict, Any

from agents.state import AgentState
from tools.poi_search_tool import poi_search_tool

logger = logging.getLogger("coupletrip")

_CURATED_CACHE: list[dict] | None = None


def _load_curated() -> list[dict]:
    """Load curated POIs from JSON file (cached after first load)."""
    global _CURATED_CACHE
    if _CURATED_CACHE is not None:
        return _CURATED_CACHE
    curated_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "curated_pois.json")
    try:
        with open(curated_path, "r", encoding="utf-8") as f:
            _CURATED_CACHE = json.load(f)
    except Exception as exc:
        logger.warning("Failed to load curated_pois.json: %s", exc)
        _CURATED_CACHE = []
    return _CURATED_CACHE


def _filter_curated(curated: list[dict], city: str, preferences: list[str]) -> list[dict]:
    """Filter curated POIs by city and optionally by preference overlap."""
    matched = [p for p in curated if p.get("city") == city]
    if preferences:
        pref_set = {p.strip() for p in preferences if p.strip()}
        # Prefer items that match at least one preference, but keep others too
        matched.sort(
            key=lambda p: -len(pref_set & set(p.get("preferences", [])))
        )
    return matched


async def search_poi(state: AgentState) -> Dict[str, Any]:
    """Search attractions: curated first, Amap supplements.

    P2.2: curated items are prioritised and marked with source='curated'.
    Amap items fill remaining slots up to 12 total.
    """
    params = state.get("parsed_params", {})
    destination = params.get("destination", "")
    preferences = params.get("preferences", [])
    pref_str = ",".join(preferences) if preferences else ""

    warnings: list = []

    # ── Phase 1: curated POIs ────────────────────────────────────
    curated_all = _load_curated()
    curated_matches = _filter_curated(curated_all, destination, preferences)

    # Normalise curated items to match poi_search_tool output shape
    curated_pois = []
    for item in curated_matches:
        curated_pois.append({
            "name": item["name"],
            "type": item["type"],
            "rating": item.get("rating", 0),
            "cost": item.get("cost", 0),
            "location": item.get("location", ""),
            "indoor": item.get("indoor", False),
            "couple_score": item.get("rating", 0) * 2,  # simple mapping for curated
            "duration_min": item.get("duration_min", 120),
            "description": item.get("description", ""),
            "source": "curated",
        })

    # ── Phase 2: Amap to supplement ──────────────────────────────
    amap_pois = []
    try:
        result = poi_search_tool.invoke({
            "city": destination,
            "preferences": pref_str,
        })
        amap_pois = json.loads(result)
    except Exception as exc:
        warnings.append(f"景点搜索失败，已降级处理: {exc}")
        logger.warning("POI search failed for %s: %s", destination, exc, exc_info=True)

    # Mark Amap items as non-curated
    for p in amap_pois:
        if "source" not in p:
            p["source"] = "amap"

    # Merge: curated first (dedup by name), then Amap
    curated_names = {p["name"] for p in curated_pois}
    amap_extra = [p for p in amap_pois if p["name"] not in curated_names]
    candidates = curated_pois + amap_extra

    # Trim to 12
    candidates = candidates[:12]

    return {
        "poi_list": candidates,
        "warnings": warnings,
        "current_phase": "search_poi",
    }
