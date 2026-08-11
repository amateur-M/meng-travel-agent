"""Maps Tool — LangChain-compatible route planning utility.

Computes optimal travel routes between coordinates.
Uses haversine distance + simple transit estimation as mock;
API interface reserved for future (Amap / Google Maps Directions).
"""

import json
import math
from typing import List, Tuple

from langchain_core.tools import tool


# ── Haversine distance ───────────────────────────────────────────

def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate the great-circle distance in kilometers."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ── Transit time estimation ──────────────────────────────────────

def _estimate_transit(distance_km: float) -> dict:
    """Estimate transit time by different modes."""
    drive_speed = 50.0
    transit_speed = 30.0
    walk_speed = 5.0

    drive_min = round(distance_km / drive_speed * 60)
    transit_min = round(distance_km / transit_speed * 60 + 10)
    walk_min = round(distance_km / walk_speed * 60)

    return {
        "distance_km": round(distance_km, 1),
        "drive": {"duration_min": drive_min, "method": "Driving"},
        "transit": {"duration_min": transit_min, "method": "Transit"},
        "walk": {"duration_min": walk_min, "method": "Walking"} if walk_min <= 60 else None,
    }


# ── Greedy nearest-neighbor route ────────────────────────────────

def _optimal_route(points: List[Tuple[float, float, str]]) -> dict:
    """Compute a simple nearest-neighbor route between POIs."""
    if len(points) < 2:
        return {
            "route": [p[2] for p in points],
            "segments": [],
            "total_distance_km": 0.0,
            "total_drive_min": 0,
            "total_transit_min": 0,
        }

    remaining = list(points[1:])
    current = points[0]
    ordered = [current]
    segments = []
    total_dist = 0.0

    while remaining:
        best_idx = 0
        best_dist = float("inf")
        for i, pt in enumerate(remaining):
            d = _haversine(current[0], current[1], pt[0], pt[1])
            if d < best_dist:
                best_dist = d
                best_idx = i
        next_pt = remaining.pop(best_idx)
        transit = _estimate_transit(best_dist)
        segments.append({
            "from": current[2],
            "to": next_pt[2],
            **transit,
        })
        total_dist += best_dist
        ordered.append(next_pt)
        current = next_pt

    return {
        "route": [p[2] for p in ordered],
        "segments": segments,
        "total_distance_km": round(total_dist, 1),
        "total_drive_min": round(total_dist / 50.0 * 60),
        "total_transit_min": round(total_dist / 30.0 * 60 + (len(segments) * 10)),
    }


# ── LangChain Tool ───────────────────────────────────────────────

@tool
def maps_tool(coordinates: str) -> str:
    """Calculate optimal route and transit times between multiple coordinate points.

    Args:
        coordinates: JSON string in format [{"name": "Place", "lat": 25.6, "lng": 100.2}, ...]
                     Names label nodes in the output route.

    Returns:
        JSON string containing ordered route, per-segment distances and transit times.
    """
    try:
        raw = json.loads(coordinates)
    except json.JSONDecodeError:
        return json.dumps({"error": "coordinates must be a valid JSON array"}, ensure_ascii=False)

    if not isinstance(raw, list) or len(raw) == 0:
        return json.dumps({"error": "coordinates must be a non-empty array"}, ensure_ascii=False)

    points: List[Tuple[float, float, str]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            return json.dumps({"error": f"Element {i} is not an object"}, ensure_ascii=False)
        name = item.get("name", f"Place {i+1}")
        lat = item.get("lat")
        lng = item.get("lng")
        if lat is None or lng is None:
            return json.dumps({"error": f"{name} missing lat or lng field"}, ensure_ascii=False)
        points.append((float(lat), float(lng), name))

    result = _optimal_route(points)
    return json.dumps(result, ensure_ascii=False)
