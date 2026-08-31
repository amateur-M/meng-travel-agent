"""Amap (高德地图) real-data service for POI, restaurant, and route lookup.

The backend previously used local mock databases for attractions and
restaurants, plus haversine-only route estimates.  This module replaces those
with the Amap Web Service API so every recommendation comes from live data.
"""

import httpx

from config.settings import settings


AMAP_BASE_URL = "https://restapi.amap.com/v3"


# GB/T 2260 administrative division codes for the destinations offered by the
# frontend.  These are stable geographic codes, not sample data.
CITY_ADCODE: dict[str, str] = {
    "大理": "532901",
    "大理市": "532901",
    "丽江": "530700",
    "丽江市": "530700",
    "三亚": "460200",
    "三亚市": "460200",
    "厦门": "350200",
    "厦门市": "350200",
    "杭州": "330100",
    "杭州市": "330100",
    "重庆": "500000",
    "重庆市": "500000",
    "北京": "110100",
    "上海": "310100",
    "广州": "440100",
    "深圳": "440300",
    "成都": "510100",
}


def resolve_adcode(city: str) -> str:
    """Map a destination name to its Amap adcode, passing unknowns through."""
    city = (city or "").strip()
    return CITY_ADCODE.get(city, city)


def _require_key() -> str:
    key = settings.maps_api_key
    if not key:
        raise RuntimeError("MAPS_API_KEY 未配置")
    return key


def search_pois(city: str, types: str, offset: int = 20) -> list[dict]:
    """Return raw Amap POI records for a city and POI category codes."""
    key = _require_key()
    response = httpx.get(
        f"{AMAP_BASE_URL}/place/text",
        params={
            "key": key,
            "types": types,
            "city": resolve_adcode(city),
            "offset": str(offset),
            "page": "1",
            "extensions": "all",
        },
        timeout=15.0,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("status") != "1":
        raise RuntimeError(f"高德地点搜索失败: {data.get('info') or '未知错误'}")

    return data.get("pois") or []


def driving_route(origin: str, destination: str) -> dict:
    """Return the first real driving route path between two lng,lat strings."""
    key = _require_key()
    response = httpx.get(
        f"{AMAP_BASE_URL}/direction/driving",
        params={
            "key": key,
            "origin": origin,
            "destination": destination,
            "extensions": "base",
        },
        timeout=15.0,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("status") != "1":
        raise RuntimeError(f"高德路线规划失败: {data.get('info') or '未知错误'}")

    paths = (data.get("route") or {}).get("paths") or []
    if not paths:
        raise RuntimeError("高德路线规划返回为空")

    return paths[0]
