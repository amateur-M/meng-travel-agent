"""POI Search Tool — live attraction discovery via Amap (高德地图)."""

import json

from langchain_core.tools import tool

from services import amap


# Attractions and museums cover both outdoor sightseeing and indoor cultural
# alternatives, which the weather-adaptation node needs for rainy days.
_ATTRACTION_TYPES = "110000|140100"

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


def _couple_score(category: str, rating: float, indoor: bool = False,
                  preferences: str = "") -> float:
    """P2.1: rating-led scoring algorithm.

    Weight breakdown:
      - rating:         0.5  (normalised 0–10 from 0–5 scale)
      - type match:     0.3  (how well category matches user preferences)
      - indoor/season:  0.2  (indoor bonus in cold seasons, outdoor bonus in warm)

    Returns a float in [0, 10].
    """
    # ── rating component (0.5 weight) ───────────────────────────
    # Map 0–5 rating to 0–10, defaulting to 5.0 (→ score 5) when no rating
    rating_norm = (rating / 5.0) if rating > 0 else 0.5
    rating_score = rating_norm * 10  # 0–10

    # ── type-match component (0.3 weight) ───────────────────────
    type_score = 5.0  # neutral baseline
    if preferences:
        pref_tags = {
            tag.strip()
            for tag in preferences.replace("，", ",").split(",")
            if tag.strip()
        }
        matched = any(
            category in _PREFERENCE_CATEGORIES.get(tag, set())
            for tag in pref_tags
        )
        if matched:
            type_score = 8.0
        else:
            type_score = 4.0
    else:
        # No preferences specified — slight boost for naturally romantic types
        type_score = 7.0 if category in ("自然", "人文") else 5.0

    # ── indoor/season component (0.2 weight) ────────────────────
    # Indoor POIs get a small bonus for weather resilience;
    # Outdoor POIs get a small bonus for scenic variety.
    # This is a static heuristic (no real-time weather context here).
    season_score = 7.0 if indoor else 6.5  # indoor slightly more versatile

    # ── weighted blend ──────────────────────────────────────────
    final = (
        rating_score * 0.5
        + type_score * 0.3
        + season_score * 0.2
    )
    return round(max(0.0, min(10.0, final)), 1)


def _duration(category: str) -> int:
    return {"文化": 90, "网红": 60, "户外": 180}.get(category, 120)


def _description(item: dict, category: str) -> str:
    keytag = item.get("keytag") or item.get("tag") or ""
    address = item.get("address") or item.get("business_area") or ""
    fallback = item.get("type", "").split(";", 1)[0] if item.get("type") else ""
    lead = keytag or fallback or category
    return f"{lead}，位于{address}" if address else lead


def _normalise_poi(item: dict, preferences: str = "") -> dict:
    typecode = item.get("typecode", "")
    type_text = item.get("type", "")
    category = _simplify_type(typecode, type_text)
    rating = _rating(item)
    indoor = _is_indoor(typecode, type_text)

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
        "indoor": indoor,
        "couple_score": _couple_score(category, rating, indoor, preferences),
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
        _normalise_poi(item, preferences)
        for item in amap.search_pois(city, _ATTRACTION_TYPES, 20)
    ]

    # P2.1: couple_score now incorporates preference matching,
    # so a single sort by couple_score suffices.
    pois.sort(key=lambda poi: -poi["couple_score"])

    return json.dumps(pois[:12], ensure_ascii=False)
