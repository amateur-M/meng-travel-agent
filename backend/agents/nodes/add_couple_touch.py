"""add_couple_touch — Attach romantic couple messages to each activity.

M2: tries LLM-powered message generation via COUPLE_COPY_PROMPT
for richer emotional variety. Falls back to M1 template bank.
"""

import json
from typing import Dict, Any, List

from agents.state import AgentState
from prompts import COUPLE_MESSAGE_PROMPT, COUPLE_COPY_PROMPT
from services.llm import call_llm


def _fill_prompt(template: str, **kwargs) -> str:
    """Fill template placeholders using str.replace (avoids JSON {} conflict)."""
    result = template
    for key, val in kwargs.items():
        result = result.replace("{" + key + "}", str(val))
    return result


# ── Message templates by activity type (M1 fallback) ─────────────

_TEMPLATES: Dict[str, List[str]] = {
    "自然": [
        "和你一起看{name}，风也温柔，云也温柔。",
        "{name}很美，但你比风景更让我心动。",
        "在{name}面前许个愿——希望每次旅行，身边都是你。",
    ],
    "人文": [
        "牵你的手走过{name}，像走过一段旧时光。",
        "{name}的故事很多，我只想写一个关于我们的。",
    ],
    "美食": [
        "{name}的味道会忘记，但和你一起吃的感觉不会。",
        "人间有味是清欢——尤其是和你分享{name}的时候。",
        "今后的每一顿饭，都想坐在你对面。",
    ],
    "文化": [
        "在{name}里，时间慢下来，刚好够我想你。",
        "艺术和美都需要慢慢看——就像你。",
    ],
    "留白": [
        "什么都不做，只是和你在一起，就是最好的时光。",
        "陪你发呆，是我旅行中最珍惜的安排。",
    ],
    "室内": [
        "外面下着雨，但{name}里有你，就是晴天。",
        "在{name}躲一场雨，顺便躲进你的眼睛里。",
    ],
    "户外": [
        "和你一起走过{name}，每一步都是风景。",
    ],
    "冒险": [
        "和你一起冒险的感觉，比{name}本身更让人心跳。",
    ],
    "景点": [
        "{name}——又一个想和你一起看尽的世界角落。",
    ],
}


def _pick_message(act_name: str, act_type: str) -> str:
    """Select a template-based couple message for the given activity."""
    import random
    templates = _TEMPLATES.get(act_type, _TEMPLATES["景点"])
    template = random.choice(templates)
    return template.format(name=act_name)


def _generate_llm_message(destination: str, act_name: str, act_type: str, period: str, weather: str) -> str | None:
    """Try to generate a couple message via LLM. Returns None on failure."""
    prompt = _fill_prompt(
        COUPLE_COPY_PROMPT,
        destination=destination,
        activity_name=act_name,
        activity_type=act_type,
        period=period,
        weather_condition=weather,
    )
    try:
        result = call_llm(
            system_prompt="你是一个温柔细腻的情感文案写手。请直接输出一句情侣寄语，不要加任何前缀或后缀。",
            user_prompt=prompt,
            mock_response={},
        )
        text = result.get("message", result.get("text", ""))
        if text:
            # Ensure 8-25 chars
            if len(text) > 25:
                # Try to find last complete clause
                for sep in ("。", "，", ".", ","):
                    idx = text[:25].rfind(sep)
                    if idx > 8:
                        text = text[:idx + 1]
                        break
                else:
                    text = text[:25]
            if len(text) >= 6:
                return text
    except Exception:
        pass
    return None


def add_couple_touch(state: AgentState) -> Dict[str, Any]:
    """Append a couple_note to every activity in the draft itinerary.

    M2: tries LLM-generated messages first via COUPLE_COPY_PROMPT.
    Falls back to M1 template bank when API key is absent.

    Returns:
        Partial state with draft_itinerary activities enriched,
        and couple_notes list populated.
    """
    params = state.get("parsed_params", {})
    destination = params.get("destination", "")
    weather = state.get("weather_data", {})
    draft = state.get("draft_itinerary", {})
    all_notes: List[str] = []

    for day_data in draft.get("days", []):
        day_idx = day_data.get("day_index", 0)
        date_key = list(weather.keys())[day_idx] if day_idx < len(weather) else ""
        w = weather.get(date_key, {})
        day_notes: List[str] = []

        for act in day_data.get("activities", []):
            act_name = act["name"]
            act_type = act.get("type", "景点")
            period = act.get("period", "上午")

            # Try LLM first
            note = _generate_llm_message(
                destination, act_name, act_type, period, w.get("condition", "晴")
            )
            if note is None:
                note = _pick_message(act_name, act_type)

            act["couple_note"] = note
            day_notes.append(note)

        if day_notes:
            all_notes.append(day_notes[0])

    return {
        "draft_itinerary": draft,
        "couple_notes": all_notes,
        "current_phase": "add_couple_touch",
    }
