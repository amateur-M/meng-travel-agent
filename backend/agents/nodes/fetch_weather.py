"""fetch_weather — Retrieve weather forecasts for trip dates.

M1 placeholder: returns mock weather data keyed by date.
M2 will replace this with a real API call (OpenWeatherMap / 和风天气).
"""

from typing import Dict, Any
from datetime import date, timedelta

from agents.state import AgentState


def fetch_weather(state: AgentState) -> Dict[str, Any]:
    """Look up weather for the destination + date range.

    In M1 this node returns hard-coded mock data so the rest of the
    pipeline can be exercised without an API key.

    Returns:
        Partial state with weather_data populated.
    """
    params = state.get("parsed_params", {})
    start_str = params.get("start_date", "")
    num_days = params.get("num_days", 1)

    weather: Dict[str, dict] = {}

    try:
        sd = date.fromisoformat(str(start_str))
    except (ValueError, TypeError):
        sd = date.today()

    # ── mock weather rotation ────────────────────────────────────
    conditions = ["晴", "晴转多云", "多云", "小雨", "晴", "晴", "多云"]
    for i in range(num_days):
        day = sd + timedelta(days=i)
        key = day.isoformat()
        cond = conditions[i % len(conditions)]
        weather[key] = {
            "condition": cond,
            "high": 26.0 + i,
            "low": 16.0 + i,
            "humidity": 55 + i * 3,
            "wind": "微风",
        }

    return {
        "weather_data": weather,
        "current_phase": "fetch_weather",
    }
