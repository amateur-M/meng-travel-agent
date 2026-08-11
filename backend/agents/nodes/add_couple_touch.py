"""add_couple_touch — Attach romantic couple messages to each activity.

For M1, generates simple template-based messages without calling the LLM.
M5 will upgrade this to GPT-powered message generation for richer variety.
"""

from typing import Dict, Any, List

from agents.state import AgentState


# ── Message templates by activity type ───────────────────────────

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


def add_couple_touch(state: AgentState) -> Dict[str, Any]:
    """Append a couple_note to every activity in the draft itinerary.

    In M1 this uses a simple template bank.
    M5 upgrades to LLM-generated messages with richer emotional range.

    Returns:
        Partial state with draft_itinerary activities enriched,
        and couple_notes list populated.
    """
    draft = state.get("draft_itinerary", {})
    all_notes: List[str] = []

    for day_data in draft.get("days", []):
        day_notes: List[str] = []
        for act in day_data.get("activities", []):
            note = _pick_message(act["name"], act.get("type", "景点"))
            act["couple_note"] = note
            day_notes.append(note)

        if day_notes:
            all_notes.append(day_notes[0])  # collect one highlight per day

    return {
        "draft_itinerary": draft,
        "couple_notes": all_notes,
        "current_phase": "add_couple_touch",
    }
