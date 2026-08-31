"""Maps Tool — real driving-route planning via Amap (高德地图)."""

import json
import math

from langchain_core.tools import tool

from services import amap


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return the great-circle distance in kilometers between two points."""
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + (
        math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _order_points(points: list[dict]) -> list[dict]:
    """Order points greedily to keep the route compact.

    Haversine distance is used only to choose visit order; every reported
    distance and duration comes from the real Amap driving API below.
    """
    if len(points) < 3:
        return list(points)

    remaining = list(points[1:])
    ordered = [points[0]]
    while remaining:
        best_index = 0
        best_distance = float("inf")
        last = ordered[-1]
        for index, point in enumerate(remaining):
            distance = _haversine(
                last["lat"], last["lng"], point["lat"], point["lng"]
            )
            if distance < best_distance:
                best_distance = distance
                best_index = index
        ordered.append(remaining.pop(best_index))
    return ordered


def _segment(origin: dict, destination: dict) -> dict:
    path = amap.driving_route(
        f"{origin['lng']},{origin['lat']}",
        f"{destination['lng']},{destination['lat']}",
    )
    distance_km = round(float(path.get("distance", 0)) / 1000, 1)
    duration_min = round(float(path.get("duration", 0)) / 60)
    return {
        "from": origin["name"],
        "to": destination["name"],
        "distance_km": distance_km,
        "drive": {"duration_min": duration_min, "method": "Driving"},
    }


@tool
def maps_tool(coordinates: str) -> str:
    """计算多个坐标点之间的真实驾车路线与耗时。

    参数:
        coordinates: JSON字符串，格式为
            [{"name": "地点", "lat": 25.6, "lng": 100.2}, ...]

    返回:
        JSON字符串，包含有序路线、每段真实距离与驾车耗时。数据来自高德地图。
    """
    try:
        raw = json.loads(coordinates)
    except json.JSONDecodeError:
        return json.dumps(
            {"error": "coordinates must be a valid JSON array"},
            ensure_ascii=False,
        )

    if not isinstance(raw, list) or not raw:
        return json.dumps(
            {"error": "coordinates must be a non-empty array"},
            ensure_ascii=False,
        )

    points: list[dict] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            return json.dumps(
                {"error": f"Element {index} is not an object"},
                ensure_ascii=False,
            )
        name = item.get("name", f"Place {index + 1}")
        lat = item.get("lat")
        lng = item.get("lng")
        if lat is None or lng is None:
            return json.dumps(
                {"error": f"{name} missing lat or lng field"},
                ensure_ascii=False,
            )
        points.append({"name": name, "lat": float(lat), "lng": float(lng)})

    ordered = _order_points(points)
    if len(ordered) < 2:
        return json.dumps(
            {
                "route": [point["name"] for point in ordered],
                "segments": [],
                "total_distance_km": 0.0,
                "total_drive_min": 0,
            },
            ensure_ascii=False,
        )

    segments = [
        _segment(ordered[index], ordered[index + 1])
        for index in range(len(ordered) - 1)
    ]

    result = {
        "route": [point["name"] for point in ordered],
        "segments": segments,
        "total_distance_km": round(
            sum(segment["distance_km"] for segment in segments), 1
        ),
        "total_drive_min": sum(
            segment["drive"]["duration_min"] for segment in segments
        ),
    }
    return json.dumps(result, ensure_ascii=False)
