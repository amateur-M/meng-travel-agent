"""POI Search Tool — live attraction discovery via Amap (高德地图)."""

import json

from langchain_core.tools import tool

from services import amap


# Attractions and museums cover both outdoor sightseeing and indoor cultural
# alternatives, which the weather-adaptation node needs for rainy days.
_ATTRACTION_TYPES = "110000|140100"

_CATEGORY_BASE_SCORE = {
    "自然": 8.5,
    "文化": 6.8,
    "网红": 6.2,
    "户外": 7.5,
    "人文": 8.0,
    "景点": 7.6,
}

_PREFERENCE_CATEGORIES: dict[str, set[str]] = {
    "浪漫": {"自然", "人文", "网红"},
    "自然": {"自然"},
    "文化": {"文化"},
    "户外": {"户外", "自然"},
    "室内": {"文化", "网红"},
    "冒险": {"户外"},
}

_INDOOR_CODES = {"140100", "140200", "140300", "060000"}


def _simplify_type(typecode: str, type_text: str) -> str:
    codes = {code for code in (typecode or "").split("|") if code}

    if "140100" in codes or "140200" in codes or "140300" in codes:
        return "文化"
    if "060000" in codes:
        return "网红"
    if "080000" in codes:
        return "户外"
    if "110205" in codes:
        return "文化"
    if any(code.startswith("1101") for code in codes):
        return "自然"
    if any(code.startswith("1102") for code in codes):
        return "自然"
    if any(code.startswith("110") for code in codes):
        return "景点"

    if "博物馆" in type_text or "会展" in type_text or "科技馆" in type_text:
        return "文化"
    if "公园" in type_text or "风景" in type_text:
        return "自然"
    return "景点"


def _is_indoor(typecode: str, type_text: str) -> bool:
    codes = {code for code in (typecode or "").split("|") if code}
    if codes & _INDOOR_CODES:
        return True
    return any(
        token in type_text for token in ("博物馆", "会展", "科技馆", "商场", "购物")
    )


def _rating(item: dict) -> float:
    raw = (item.get("biz_ext") or {}).get("rating")
    try:
        return round(float(raw or 0), 1)
    except (TypeError, ValueError):
        return 0.0


def _couple_score(category: str, rating: float) -> float:
    base = _CATEGORY_BASE_SCORE.get(category, 7.0)
    if rating:
        base += max(-1.0, min(1.0, (rating - 4.0) * 0.5))
    return round(max(0.0, min(10.0, base)), 1)


def _duration(category: str) -> int:
    return {"文化": 90, "网红": 60, "户外": 180}.get(category, 120)


def _description(item: dict, category: str) -> str:
    keytag = item.get("keytag") or item.get("tag") or ""
    address = item.get("address") or item.get("business_area") or ""
    fallback = item.get("type", "").split(";", 1)[0] if item.get("type") else ""
    lead = keytag or fallback or category
    return f"{lead}，位于{address}" if address else lead


def _normalise_poi(item: dict) -> dict:
    typecode = item.get("typecode", "")
    type_text = item.get("type", "")
    category = _simplify_type(typecode, type_text)
    rating = _rating(item)

    location = item.get("location", "")
    lat = lng = None
    if location:
        try:
            lng_text, lat_text = location.split(",", 1)
            lng, lat = float(lng_text), float(lat_text)
        except ValueError:
            lng = lat = None

    return {
        "name": item.get("name", ""),
        "type": category,
        "rating": rating,
        "cost": 0.0,
        "location": item.get("address") or item.get("business_area") or "",
        "indoor": _is_indoor(typecode, type_text),
        "couple_score": _couple_score(category, rating),
        "duration_min": _duration(category),
        "description": _description(item, category),
        "lat": lat,
        "lng": lng,
        "photos": [
            photo.get("url")
            for photo in (item.get("photos") or [])
            if photo.get("url")
        ],
    }


def _preference_score(poi: dict, preferences: str) -> int:
    if not preferences:
        return 0

    tags = {
        tag.strip()
        for tag in preferences.replace("，", ",").split(",")
        if tag.strip()
    }
    score = 0
    for tag in tags:
        if poi["type"] in _PREFERENCE_CATEGORIES.get(tag, set()):
            score += 2
    return score


@tool
def poi_search_tool(city: str, preferences: str = "") -> str:
    """搜索指定城市的景点，按情侣旅行偏好排序。

    参数:
        city: 城市名称，如"大理"、"三亚"、"杭州"。
        preferences: 偏好标签，逗号分隔，例如"浪漫,自然,文化"。留空则按推荐度排序。

    返回:
        JSON数组字符串，每个景点包含名称、类型、评分、位置、室内/室外标记、
        情侣推荐指数和描述。数据来自高德地图实时接口。
    """
    pois = [
        _normalise_poi(item)
        for item in amap.search_pois(city, _ATTRACTION_TYPES, 20)
    ]

    if preferences:
        pois.sort(
            key=lambda poi: (
                -_preference_score(poi, preferences),
                -poi["couple_score"],
            )
        )
    else:
        pois.sort(key=lambda poi: -poi["couple_score"])

    return json.dumps(pois[:12], ensure_ascii=False)
