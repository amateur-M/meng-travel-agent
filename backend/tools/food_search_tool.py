"""Food Search Tool — live restaurant discovery via Amap (高德地图)."""

import json

from langchain_core.tools import tool

from services import amap


_RESTAURANT_TYPES = "050000"


def _rating(item: dict) -> float:
    raw = (item.get("biz_ext") or {}).get("rating")
    try:
        return round(float(raw or 0), 1)
    except (TypeError, ValueError):
        return 0.0


def _avg_cost(item: dict) -> float:
    raw = (item.get("biz_ext") or {}).get("cost")
    try:
        return round(float(raw or 0), 1)
    except (TypeError, ValueError):
        return 0.0


def _cuisine(typecode: str, type_text: str, tag: str) -> str:
    combined = f"{type_text} {tag}"
    if "火锅" in combined:
        return "火锅"

    codes = {code for code in (typecode or "").split("|") if code}
    if "050200" in codes:
        return "西餐"
    if "050300" in codes:
        return "快餐"
    if "050500" in codes:
        return "咖啡"
    if "050700" in codes:
        return "糕点"
    if "050800" in codes:
        return "甜品"
    if "050600" in codes:
        return "冷饮"
    if "050900" in codes:
        return "本地菜"
    if "050100" in codes:
        return "中餐"
    return "本地菜"


def _couple_score(cuisine: str, rating: float) -> float:
    base = 7.0
    if cuisine in ("火锅", "本地菜", "西餐"):
        base += 0.5
    if rating:
        base += max(-1.0, min(1.0, (rating - 4.0) * 0.5))
    return round(max(0.0, min(10.0, base)), 1)


def _normalise_restaurant(item: dict) -> dict:
    typecode = item.get("typecode", "")
    type_text = item.get("type", "")
    tag = item.get("keytag") or item.get("tag") or ""
    cuisine = _cuisine(typecode, type_text, tag)
    rating = _rating(item)

    return {
        "name": item.get("name", ""),
        "cuisine": cuisine,
        "rating": rating,
        "avg_cost": _avg_cost(item),
        "location": item.get("address") or item.get("business_area") or "",
        "atmosphere": [tag] if tag else [],
        "couple_score": _couple_score(cuisine, rating),
    }


def _cuisine_score(restaurant: dict, cuisine: str) -> float:
    if not cuisine or cuisine == "不限":
        return 0.0

    text = f"{restaurant['name']} {restaurant['cuisine']} "
    text += " ".join(restaurant.get("atmosphere", []))
    if cuisine in text or restaurant["cuisine"] in cuisine:
        return 3.0
    return 0.0


@tool
def food_search_tool(
    city: str,
    cuisine: str = "不限",
    budget_per_person: float = 0.0,
) -> str:
    """搜索指定城市的餐厅，按菜系与人均预算筛选。

    参数:
        city: 城市名称，如"大理"、"三亚"。
        cuisine: 菜系偏好，如"中餐"、"火锅"、"西餐"，"不限"表示不筛选。
        budget_per_person: 人均预算上限（元），0 表示不限制。

    返回:
        JSON数组字符串，每个餐厅包含名称、菜系、评分、人均消费、位置和氛围标签。
        数据来自高德地图实时接口。
    """
    restaurants = [
        _normalise_restaurant(item)
        for item in amap.search_pois(city, _RESTAURANT_TYPES, 30)
    ]

    if budget_per_person > 0:
        restaurants = [
            restaurant
            for restaurant in restaurants
            if restaurant["avg_cost"] <= budget_per_person
        ]

    restaurants.sort(
        key=lambda restaurant: (
            -_cuisine_score(restaurant, cuisine),
            -restaurant["couple_score"],
        )
    )

    return json.dumps(restaurants[:12], ensure_ascii=False)
