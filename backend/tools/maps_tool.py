"""Maps Tool — LangChain-compatible route planning utility.

Computes optimal travel routes between coordinates.
Uses haversine distance + simple transit estimation as mock;
API interface reserved for future (高德/Google Maps Directions).
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
    # Driving: ~40 km/h in city, ~60 km/h highway
    drive_speed = 50.0
    # Public transit: slower, with wait time
    transit_speed = 30.0
    # Walking: 5 km/h
    walk_speed = 5.0

    drive_min = round(distance_km / drive_speed * 60)
    transit_min = round(distance_km / transit_speed * 60 + 10)  # +10 min wait
    walk_min = round(distance_km / walk_speed * 60)

    return {
        "distance_km": round(distance_km, 1),
        "drive": {"duration_min": drive_min, "method": "驾车"},
        "transit": {"duration_min": transit_min, "method": "公共交通"},
        "walk": {"duration_min": walk_min, "method": "步行"} if walk_min <= 60 else None,
    }


# ── Greedy nearest-neighbor route ────────────────────────────────

def _optimal_route(points: List[Tuple[float, float, str]]) -> dict:
    """Compute a simple nearest-neighbor route between POIs.

    Args:
        points: List of (lat, lng, name) tuples.

    Returns:
        dict with ordered route and cumulative distances/times.
    """
    if len(points) < 2:
        return {
            "route": points,
            "segments": [],
            "total_distance_km": 0.0,
            "total_drive_min": 0,
            "total_transit_min": 0,
        }

    # Start from first point; visit nearest unvisited next
    remaining = list(points[1:])
    current = points[0]
    ordered = [current]
    segments = []
    total_dist = 0.0

    while remaining:
        # Find nearest
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
    """根据多个坐标点计算最优路线和交通时间。

    参数:
        coordinates: JSON字符串，格式为 [{"name": "景点名", "lat": 25.6, "lng": 100.2}, ...]
                     名称用于标注输出路线中的节点。

    返回:
        JSON字符串，包含最优路线顺序、每段路程的距离和不同交通方式的预估时间。
    """
    try:
        raw = json.loads(coordinates)
    except json.JSONDecodeError:
        return json.dumps({"error": "coordinates 参数必须是有效的 JSON 数组"}, ensure_ascii=False)

    if not isinstance(raw, list) or len(raw) == 0:
        return json.dumps({"error": "coordinates 必须是非空数组"}, ensure_ascii=False)

    points: List[Tuple[float, float, str]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            return json.dumps({"error": f"第{i}个元素不是对象"}, ensure_ascii=False)
        name = item.get("name", f"地点{i+1}")
        lat = item.get("lat")
        lng = item.get("lng")
        if lat is None or lng is None:
            return json.dumps({"error": f"{name} 缺少 lat 或 lng 字段"}, ensure_ascii=False)
        points.append((float(lat), float(lng), name))

    result = _optimal_route(points)
    return json.dumps(result, ensure_ascii=False)
