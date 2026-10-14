"""fetch_weather — Retrieve weather forecasts for trip dates.

M2: delegates to weather_tool which tries QWeather (和风天气) first,
falls back to a 12-city seasonal mock database on failure.
"""

from datetime import date, timedelta
from typing import Dict, Any

from agents.state import AgentState
from tools.weather_tool import weather_tool_sync


async def fetch_weather(state: AgentState) -> Dict[str, Any]:
    """Look up weather for the destination + date range.

    Uses num_days from parsed_params to determine how many forecast
    days to fetch, starting from start_date.

    Returns:
        Partial state with weather_data populated.
    """
    params = state.get("parsed_params", {})
    destination = params.get("destination", "")
    start_str = params.get("start_date", "")
    num_days = params.get("num_days", 1)

    # Compute end_date from start + num_days (weather for travel days only)
    try:
        sd = date.fromisoformat(str(start_str))
        end_str = (sd + timedelta(days=num_days - 1)).isoformat()
    except (ValueError, TypeError):
        from datetime import date as dt
        sd = dt.today()
        # P4 fix: write back the corrected start_str so weather_tool_sync
        # receives a valid ISO date instead of the original malformed value.
        start_str = sd.isoformat()
        end_str = (sd + timedelta(days=num_days - 1)).isoformat()

    weather_data = weather_tool_sync(destination, start_str, end_str)

    return {
        "weather_data": weather_data,
        "current_phase": "fetch_weather",
    }
