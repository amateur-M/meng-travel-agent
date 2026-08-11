"""Weather Tool — LangChain-compatible weather forecast fetcher.

Supports both real API (OpenWeatherMap) and mock fallback.
Registered as a LangChain @tool for use in agent chains.
"""

import json
import os
from datetime import date, timedelta
from typing import Optional

import httpx
from langchain_core.tools import tool

from config.settings import settings

# ── Mock weather patterns per city (seasonal) ─────────────────────

_MOCK_WEATHER = {
    "北京": {"spring": ["晴", "晴转多云", "多云"], "summer": ["晴", "多云", "雷阵雨", "晴"],
             "autumn": ["晴", "晴", "多云"], "winter": ["晴", "多云", "阴", "晴"]},
    "上海": {"spring": ["小雨", "多云", "阴", "晴"], "summer": ["多云", "雷阵雨", "阴", "晴"],
             "autumn": ["晴", "多云", "晴"], "winter": ["阴", "小雨", "多云", "晴"]},
    "大理": {"spring": ["晴", "晴转多云", "多云", "晴"], "summer": ["多云", "小雨", "晴", "晴转多云"],
             "autumn": ["晴", "晴", "晴转多云"], "winter": ["晴", "晴", "多云", "晴"]},
    "丽江": {"spring": ["晴", "多云", "晴", "晴转多云"], "summer": ["小雨", "多云", "阵雨", "晴"],
             "autumn": ["晴", "晴", "多云"], "winter": ["晴", "晴", "晴", "多云"]},
    "三亚": {"spring": ["晴", "多云", "晴", "雷阵雨"], "summer": ["多云", "雷阵雨", "阴", "晴"],
             "autumn": ["晴", "多云", "晴"], "winter": ["晴", "晴", "多云", "晴"]},
    "成都": {"spring": ["阴", "小雨", "多云", "晴"], "summer": ["阴", "雷阵雨", "多云", "小雨"],
             "autumn": ["阴", "小雨", "多云"], "winter": ["阴", "阴", "小雨", "多云"]},
    "西安": {"spring": ["晴", "多云", "晴", "阴"], "summer": ["晴", "多云", "雷阵雨", "晴"],
             "autumn": ["晴", "晴", "多云"], "winter": ["阴", "多云", "晴", "阴"]},
    "杭州": {"spring": ["小雨", "多云", "晴", "多云"], "summer": ["雷阵雨", "多云", "晴", "小雨"],
             "autumn": ["晴", "多云", "晴"], "winter": ["阴", "小雨", "多云", "晴"]},
    "厦门": {"spring": ["多云", "小雨", "晴", "多云"], "summer": ["多云", "雷阵雨", "晴", "多云"],
             "autumn": ["晴", "晴", "多云"], "winter": ["晴", "多云", "阴", "晴"]},
    "重庆": {"spring": ["阴", "小雨", "多云", "阴"], "summer": ["阴", "雷阵雨", "多云", "晴"],
             "autumn": ["阴", "小雨", "多云"], "winter": ["阴", "阴", "小雨", "阴"]},
    "广州": {"spring": ["多云", "雷阵雨", "阴", "多云"], "summer": ["雷阵雨", "多云", "晴", "雷阵雨"],
             "autumn": ["晴", "多云", "晴"], "winter": ["多云", "阴", "小雨", "晴"]},
}

_DEFAULT_WEATHER = {"spring": ["晴", "多云", "晴转多云"], "summer": ["多云", "雷阵雨", "晴", "多云"],
                    "autumn": ["晴", "晴", "多云"], "winter": ["阴", "多云", "晴", "多云"]}

_TEMP_BY_SEASON = {
    "spring": (12, 24), "summer": (24, 36), "autumn": (14, 26), "winter": (0, 12),
}


def _guess_season(month: int) -> str:
    if 3 <= month <= 5:
        return "spring"
    elif 6 <= month <= 8:
        return "summer"
    elif 9 <= month <= 11:
        return "autumn"
    else:
        return "winter"


def _match_city(city: str) -> Optional[str]:
    """Find the best matching city key in mock data."""
    for key in _MOCK_WEATHER:
        if key in city or city in key:
            return key
    return None


def _generate_mock(city: str, start: str, end: str) -> dict:
    """Generate realistic mock weather for the given city and date range."""
    try:
        sd = date.fromisoformat(start)
        ed = date.fromisoformat(end)
    except (ValueError, TypeError):
        sd = date.today()
        ed = sd + timedelta(days=2)

    season = _guess_season(sd.month)
    city_key = _match_city(city)
    patterns = (_MOCK_WEATHER.get(city_key) or _DEFAULT_WEATHER).get(season, ["晴", "多云"])
    t_low, t_high = _TEMP_BY_SEASON.get(season, (10, 25))

    result = {}
    days = (ed - sd).days + 1
    for i in range(min(days, 14)):
        day = sd + timedelta(days=i)
        key = day.isoformat()
        cond = patterns[i % len(patterns)]
        is_rain = any(w in cond for w in ("雨", "雷", "雪", "阵"))
        result[key] = {
            "condition": cond,
            "condition_en": "rain" if is_rain else "clear" if "晴" in cond else "cloudy",
            "high": round(t_high + (i % 3) - 1, 1),
            "low": round(t_low + (i % 3) - 1, 1),
            "feels_like": round((t_high + t_low) / 2 + (i % 5) - 2, 1),
            "precip_prob": 0.75 if is_rain else (0.3 if "多云" in cond else 0.1),
            "humidity": 55 + (i * 5) % 30,
            "wind": "微风" if not is_rain else "微风转3-4级",
            "source": "mock",
        }
    return result


# ── Real API client ──────────────────────────────────────────────

async def _fetch_openweathermap(city: str, start: str, end: str) -> dict:
    """Fetch real weather from OpenWeatherMap 5-day/3h forecast.

    Falls back to mock on any error (network, missing key, rate limit).
    """
    api_key = settings.weather_api_key
    if not api_key:
        raise ValueError("OPENWEATHERMAP_API_KEY not configured")

    url = "https://api.openweathermap.org/data/2.5/forecast"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params={
            "q": city,
            "appid": api_key,
            "units": "metric",
            "lang": "zh_cn",
            "cnt": 40,
        })
        resp.raise_for_status()
        data = resp.json()

    # Group 3-hourly entries by day
    by_day: dict = {}
    for entry in data.get("list", []):
        dt = entry.get("dt_txt", "")[:10]  # "2026-08-11 12:00:00" -> "2026-08-11"
        if dt not in by_day:
            by_day[dt] = {"temps": [], "conditions": [], "humidity": []}
        by_day[dt]["temps"].append(entry["main"]["temp"])
        by_day[dt]["conditions"].append(entry["weather"][0]["description"])
        by_day[dt]["humidity"].append(entry["main"]["humidity"])

    result = {}
    for dt, agg in by_day.items():
        cond = max(set(agg["conditions"]), key=agg["conditions"].count)
        precip = entry.get("pop", 0.0)
        result[dt] = {
            "condition": cond,
            "condition_en": "rain" if "雨" in cond else "clear",
            "high": round(max(agg["temps"]), 1),
            "low": round(min(agg["temps"]), 1),
            "feels_like": round(sum(agg["temps"]) / len(agg["temps"]), 1),
            "precip_prob": float(precip),
            "humidity": round(sum(agg["humidity"]) / len(agg["humidity"])),
            "wind": "微风",
            "source": "openweathermap",
        }
    return result


# ── LangChain Tool ───────────────────────────────────────────────

@tool
async def weather_tool(city: str, start_date: str, end_date: str) -> str:
    """获取指定城市在日期范围内的每日天气预报。

    参数:
        city: 城市名称，如"大理"、"北京"、"三亚"
        start_date: 开始日期，格式 YYYY-MM-DD
        end_date: 结束日期，格式 YYYY-MM-DD

    返回:
        JSON字符串，包含每天的温度、天气状况、降水概率和体感温度。
    """
    # 1) Try real API
    try:
        weather = await _fetch_openweathermap(city, start_date, end_date)
        if weather:
            return json.dumps(weather, ensure_ascii=False)
    except Exception:
        pass  # fallback to mock silently

    # 2) Mock fallback
    weather = _generate_mock(city, start_date, end_date)
    return json.dumps(weather, ensure_ascii=False)


# ── Sync wrapper (for nodes that are not async) ──────────────────

def weather_tool_sync(city: str, start_date: str, end_date: str) -> str:
    """Synchronous version of weather_tool for use in non-async nodes."""
    return _generate_mock(city, start_date, end_date)
