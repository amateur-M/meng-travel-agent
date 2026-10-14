"""plan_itinerary — Core LLM node that generates the day-by-day itinerary.

M2: uses shared LLM service (services.llm.call_llm) and the new
PLAN_ITINERARY_PROMPT from prompts/plan_itinerary_prompt.md.
Falls back to rule-based mock when API key is absent.
"""

import json
from typing import Dict, Any

from agents.state import AgentState
from prompts import SYSTEM_PROMPT, PLAN_ITINERARY_PROMPT
from services.llm import acall_llm


def _build_prompt(state: AgentState) -> str:
    """Assemble the full itinerary-generation prompt from state."""
    params = state.get("parsed_params", {})
    weather = state.get("weather_data", {})
    pois = state.get("poi_list", [])
    foods = state.get("food_list", [])

    # ── weather summary ──────────────────────────────────────────
    weather_lines = []
    for d, w in weather.items():
        weather_lines.append(
            f"  {d}: {w.get('condition', '?')}，"
            f"{w.get('high', '?')}°C / {w.get('low', '?')}°C"
        )
    weather_summary = "\n".join(weather_lines) if weather_lines else "暂无天气数据"

    # ── POI summary ──────────────────────────────────────────────
    poi_lines = [
        f"  {i+1}. {p['name']} ({p.get('type','?')}) "
        f"⭐{p.get('rating','?')} ¥{p.get('cost',0)} — {p.get('location','')}"
        + (f" [couple_score={p.get('couple_score','?')}]" if "couple_score" in p else "")
        for i, p in enumerate(pois[:8])
    ]
    poi_summary = "\n".join(poi_lines) if poi_lines else "暂无景点数据"

    # ── food summary ─────────────────────────────────────────────
    food_lines = [
        f"  {i+1}. {f['name']} ({f.get('cuisine','?')}) "
        f"⭐{f.get('rating','?')} 人均¥{f.get('avg_cost',0)}"
        + (f" [{', '.join(f.get('atmosphere', []))}]" if f.get("atmosphere") else "")
        for i, f in enumerate(foods[:6])
    ]
    food_summary = "\n".join(food_lines) if food_lines else "暂无餐厅数据"

    num_days = params.get("num_days", 1)
    budget = params.get("budget", 3000)
    daily = round(budget / max(num_days, 1), 0)

    pace = params.get("pace", "轻松")
    extra = ""
    if pace == "轻松":
        extra = "请确保每天至少有1个留白时段（如'洱海边发呆'、'古城漫步'）。"
    elif pace == "充实":
        extra = "可以适当增加活动密度，但每档仍最多2个活动。"

    replacements = {
        "{num_days}": str(num_days),
        "{destination}": str(params.get("destination", "")),
        "{start_date}": str(params.get("start_date", "")),
        "{end_date}": str(params.get("end_date", "")),
        "{budget}": str(budget),
        "{preferences}": "、".join(params.get("preferences", [])),
        "{pace}": str(pace),
        "{weather_summary}": weather_summary,
        "{poi_summary}": poi_summary,
        "{food_summary}": food_summary,
        "{daily_budget}": str(daily),
        "{extra_instructions}": extra,
    }
    prompt = PLAN_ITINERARY_PROMPT
    for key, val in replacements.items():
        prompt = prompt.replace(key, val)
    return prompt



def _mock_itinerary(state: AgentState) -> dict:
    """Fallback: generate a rule-based mock itinerary without calling LLM."""
    params = state.get("parsed_params", {})
    pois = state.get("poi_list", [])
    foods = state.get("food_list", [])
    weather = state.get("weather_data", {})
    num_days = params.get("num_days", 1)

    days = []
    for d in range(num_days):
        date_key = list(weather.keys())[d] if d < len(weather) else ""
        w = weather.get(date_key, {})

        p1 = pois[d % len(pois)] if pois else {"name": "城市漫步", "cost": 0, "type": "自然"}
        p2 = pois[(d + 1) % len(pois)] if len(pois) > 1 else {"name": "当地博物馆", "cost": 0, "type": "文化"}
        f1 = foods[d % len(foods)] if foods else {"name": "本地餐厅", "avg_cost": 60, "cuisine": "本地菜"}
        f2 = foods[(d + 1) % len(foods)] if len(foods) > 1 else {"name": "夜市小吃", "avg_cost": 30, "cuisine": "小吃"}

        day = {
            "day_index": d,
            "weather": w.get("condition", "晴"),
            "activities": [
                {"period": "上午", "name": p1["name"], "type": p1.get("type", "景点"),
                 "start_time": "09:00", "duration_min": 120,
                 "estimated_cost": p1.get("cost", 0),
                 "description": f"游览{p1['name']}",
                 "location": p1.get("location", "")},
                {"period": "上午", "name": "漫步留白", "type": "留白",
                 "start_time": "11:00", "duration_min": 60,
                 "estimated_cost": 0,
                 "description": "牵手漫步，享受二人时光",
                 "location": ""},
                {"period": "下午", "name": f1["name"], "type": "美食",
                 "start_time": "12:00", "duration_min": 90,
                 "estimated_cost": f1.get("avg_cost", 60) * 2,
                 "description": f"品尝{f1.get('cuisine','本地美食')}",
                 "location": f1.get("location", "")},
                {"period": "下午", "name": p2["name"], "type": p2.get("type", "文化"),
                 "start_time": "14:00", "duration_min": 120,
                 "estimated_cost": p2.get("cost", 0),
                 "description": f"参观{p2['name']}",
                 "location": p2.get("location", "")},
                {"period": "晚间", "name": f2["name"], "type": "美食",
                 "start_time": "18:00", "duration_min": 90,
                 "estimated_cost": f2.get("avg_cost", 30) * 2,
                 "description": f"品尝{f2.get('cuisine','本地美食')}",
                 "location": f2.get("location", "")},
                {"period": "晚间", "name": "夜游", "type": "留白",
                 "start_time": "20:00", "duration_min": 60,
                 "estimated_cost": 0,
                 "description": "夜色中漫步，享受宁静时光",
                 "location": ""},
            ],
        }
        days.append(day)

    return {"days": days}


async def plan_itinerary(state: AgentState) -> Dict[str, Any]:
    """Generate a day-by-day itinerary using the LLM.

    If OPENAI_API_KEY is configured, the real LLM is called via
    services.llm.acall_llm().  Otherwise, falls back to _mock_itinerary
    so the graph remains testable.

    Returns:
        Partial state with draft_itinerary populated.
    """
    prompt = _build_prompt(state)

    draft = await acall_llm(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=prompt,
        mock_response=_mock_itinerary(state),
    )

    return {
        "draft_itinerary": draft,
        "current_phase": "plan_itinerary",
    }
