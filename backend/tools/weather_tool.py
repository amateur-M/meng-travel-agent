"""Weather Tool — LangChain-compatible weather forecast fetcher.

Supports real APIs (QWeather/和风天气 default, OpenWeatherMap fallback)
and a mock fallback.
Registered as a LangChain @tool for use in agent chains.
"""

import json
import logging
import os
from datetime import date, timedelta
from typing import Optional

import httpx
from langchain_core.tools import tool

from config.settings import settings
from services.qweather_auth import build_qweather_headers

logger = logging.getLogger("coupletrip")

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
            by_day[dt] = {"temps": [], "conditions": [], "humidity": [], "pops": []}
        by_day[dt]["temps"].append(entry["main"]["temp"])
        by_day[dt]["conditions"].append(entry["weather"][0]["description"])
        by_day[dt]["humidity"].append(entry["main"]["humidity"])
        # P3 fix: collect pop per entry so each day gets its own max, not a stale variable
        by_day[dt]["pops"].append(float(entry.get("pop", 0.0)))

    result = {}
    for dt, agg in by_day.items():
        cond = max(set(agg["conditions"]), key=agg["conditions"].count)
        # P3 fix: use max of collected pop values for this day (was stale `entry` from outer loop)
        precip = max(agg["pops"]) if agg["pops"] else 0.0
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


# ── QWeather (和风天气) client ────────────────────────────────────

# Tidy: _parse_qweather_daily (old v7 format) removed — was dead code
# referenced only by tests.  _parse_qweather_v1_daily is the live parser.

def _condition_en(condition: str) -> str:
    """Map a Chinese QWeather condition to the shared condition enum."""
    if any(w in condition for w in ("雨", "雪", "雷", "阵")):
        return "rain"
    if "晴" in condition:
        return "clear"
    return "cloudy"


def _parse_qweather_v1_daily(days: list, start: str, end: str) -> dict:
    """Convert QWeather v1 daily forecast entries into the shared dict."""
    try:
        sd = date.fromisoformat(start)
        ed = date.fromisoformat(end)
    except (ValueError, TypeError):
        sd = date.today()
        ed = sd + timedelta(days=2)

    result: dict = {}
    for day in days:
        forecast_start = day.get("forecastStartTime", "")
        day_key = forecast_start[:10] if forecast_start else ""
        if not day_key:
            continue
        try:
            d = date.fromisoformat(day_key)
        except ValueError:
            continue
        if not (sd <= d <= ed):
            continue

        daytime = day.get("daytime", {}) or {}
        nighttime = day.get("nighttime", {}) or {}
        day_condition = (daytime.get("condition") or {}).get("text", "")
        night_condition = (nighttime.get("condition") or {}).get("text", "")
        condition = day_condition or night_condition or "晴"

        temp_max = float((day.get("temperatureMax") or {}).get("value", 0) or 0)
        temp_min = float((day.get("temperatureMin") or {}).get("value", 0) or 0)
        feels_like = float(
            (day.get("temperatureAvg") or {}).get("value", 0)
            or (temp_max + temp_min) / 2
        )

        day_precip = (daytime.get("precipitation") or {}).get("probability", 0)
        night_precip = (nighttime.get("precipitation") or {}).get("probability", 0)
        precip_prob = float(max(day_precip or 0, night_precip or 0))

        humidity = float(daytime.get("humidity", nighttime.get("humidity", 0)) or 0)
        if 0 < humidity <= 1:
            humidity = round(humidity * 100)

        wind = daytime.get("wind") or {}
        wind_scale = wind.get("scale", "")
        wind_compass = (wind.get("direction") or {}).get("compass", "")
        wind_text = f"{wind_compass}风{wind_scale}级" if wind_scale else "微风"

        result[day_key] = {
            "condition": condition,
            "condition_en": _condition_en(condition),
            "high": round(temp_max, 1),
            "low": round(temp_min, 1),
            "feels_like": round(feels_like, 1),
            "precip_prob": round(precip_prob, 2),
            "humidity": float(humidity),
            "wind": wind_text,
            "source": "qweather",
        }

    if not result:
        raise ValueError("No QWeather data in the requested date range")
    return result


def _qweather_headers() -> dict:
    """Build QWeather authentication headers for JWT or API Key."""
    return build_qweather_headers(settings)


def _forecast_days(start: str, end: str) -> int:
    """Return the number of daily forecast entries to request (max 10)."""
    try:
        # sd应该为当前日期
        sd = date.fromisoformat(date.today().isoformat())
        ed = date.fromisoformat(end)
        return max(1, min(10, (ed - sd).days + 1))
    except (ValueError, TypeError):
        return 3


async def _lookup_qweather_city(city: str) -> tuple[float, float]:
    """Resolve a city name to lat/lon with QWeather GeoAPI."""
    url = f"{settings.qweather_base_url.rstrip('/')}/geo/v2/city/lookup"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            url,
            params={"location": city, "range": "cn", "number": "5", "lang": "zh"},
            headers=_qweather_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "200" or not data.get("location"):
            raise ValueError(f"QWeather city lookup failed: {data.get('code')}")

    location = data["location"][0]
    return float(location["lat"]), float(location["lon"])


def _lookup_qweather_city_sync(city: str) -> tuple[float, float]:
    """Synchronous city-to-lat/lon lookup for QWeather GeoAPI."""
    url = f"{settings.qweather_base_url.rstrip('/')}/geo/v2/city/lookup"
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(
            url,
            params={"location": city, "range": "cn", "number": "5", "lang": "zh"},
            headers=_qweather_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "200" or not data.get("location"):
            raise ValueError(f"QWeather city lookup failed: {data.get('code')}")

    location = data["location"][0]
    return float(location["lat"]), float(location["lon"])


async def _fetch_qweather(city: str, start: str, end: str) -> dict:
    """Fetch real weather from QWeather's current JWT-authenticated API."""
    api_key = settings.weather_api_key
    if not api_key:
        raise ValueError("WEATHER_API_KEY not configured for QWeather")

    lat, lon = await _lookup_qweather_city(city)
    weather_url = f"{settings.qweather_base_url.rstrip('/')}/weather/v1/daily/{lat}/{lon}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        weather_resp = await client.get(
            weather_url,
            params={
                "days": str(_forecast_days(start, end)),
                "localTime": "true",
                "lang": "zh",
            },
            headers=_qweather_headers(),
        )
        weather_resp.raise_for_status()
        weather_data = weather_resp.json()

    daily = weather_data.get("days", [])
    if not daily:
        raise ValueError("QWeather returned empty daily forecast")

    return _parse_qweather_v1_daily(daily, start, end)


def _fetch_qweather_sync(city: str, start: str, end: str) -> dict:
    """Synchronous QWeather fetch used by the LangGraph node path."""
    api_key = settings.weather_api_key
    if not api_key:
        raise ValueError("WEATHER_API_KEY not configured for QWeather")

    lat, lon = _lookup_qweather_city_sync(city)
    weather_url = f"{settings.qweather_base_url.rstrip('/')}/weather/v1/daily/{lat}/{lon}"

    with httpx.Client(timeout=10.0) as client:
        weather_resp = client.get(
            weather_url,
            params={
                "days": str(_forecast_days(start, end)),
                "localTime": "true",
                "lang": "zh",
            },
            headers=_qweather_headers(),
        )
        weather_resp.raise_for_status()
        weather_data = weather_resp.json()

    daily = weather_data.get("days", [])
    if not daily:
        raise ValueError("QWeather returned empty daily forecast")

    return _parse_qweather_v1_daily(daily, start, end)


def _fetch_openweathermap_sync(city: str, start: str, end: str) -> dict:
    """Synchronous OpenWeatherMap fetch (legacy provider fallback)."""
    api_key = settings.weather_api_key
    if not api_key:
        raise ValueError("WEATHER_API_KEY not configured for OpenWeatherMap")

    url = "https://api.openweathermap.org/data/2.5/forecast"
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(url, params={
            "q": city,
            "appid": api_key,
            "units": "metric",
            "lang": "zh_cn",
            "cnt": 40,
        })
        resp.raise_for_status()
        data = resp.json()

    by_day: dict = {}
    for entry in data.get("list", []):
        dt = entry.get("dt_txt", "")[:10]
        by_day.setdefault(dt, {"temps": [], "conditions": [], "humidity": []})
        by_day[dt]["temps"].append(entry["main"]["temp"])
        by_day[dt]["conditions"].append(entry["weather"][0]["description"])
        by_day[dt]["humidity"].append(entry["main"]["humidity"])

    result = {}
    for dt, agg in by_day.items():
        cond = max(set(agg["conditions"]), key=agg["conditions"].count)
        result[dt] = {
            "condition": cond,
            "condition_en": "rain" if "雨" in cond else "clear",
            "high": round(max(agg["temps"]), 1),
            "low": round(min(agg["temps"]), 1),
            "feels_like": round(sum(agg["temps"]) / len(agg["temps"]), 1),
            "precip_prob": 0.5 if "雨" in cond else 0.1,
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
    # 1) Try real API (QWeather by default, OpenWeatherMap as legacy fallback)
    try:
        if settings.weather_provider == "qweather":
            weather = await _fetch_qweather(city, start_date, end_date)
        else:
            weather = await _fetch_openweathermap(city, start_date, end_date)
        if weather:
            return json.dumps(weather, ensure_ascii=False)
    except Exception:
        # P10: log the fallback instead of swallowing silently
        logger.warning(
            "Weather API (%s) failed for %s %s–%s; falling back to mock",
            settings.weather_provider, city, start_date, end_date,
            exc_info=True,
        )

    # 2) Mock fallback
    weather = _generate_mock(city, start_date, end_date)
    return json.dumps(weather, ensure_ascii=False)


# ── Sync wrapper (for nodes that are not async) ──────────────────

def weather_tool_sync(city: str, start_date: str, end_date: str) -> dict:
    """Synchronous weather lookup returning the shared weather dict."""
    try:
        if settings.weather_provider == "qweather":
            weather = _fetch_qweather_sync(city, start_date, end_date)
        else:
            weather = _fetch_openweathermap_sync(city, start_date, end_date)
        if weather:
            return weather
    except Exception:
        # P10: log the fallback instead of swallowing silently
        logger.warning(
            "Weather API (%s) failed for %s %s–%s; falling back to mock",
            settings.weather_provider, city, start_date, end_date,
            exc_info=True,
        )

    return _generate_mock(city, start_date, end_date)
