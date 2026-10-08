"""add_couple_touch — Attach romantic couple messages to each activity.

P7 fix: generates all messages in a single batch LLM call instead of one
call per activity, reducing latency from O(activities) to O(1).
Falls back to the M1 template bank when no API key is configured.
"""

import json
import logging
from typing import Dict, Any, List

from agents.state import AgentState
from services.llm import call_llm

logger = logging.getLogger("coupletrip")


# Tidy: _fill_prompt removed — was unused after P7 batch rewrite.
# COUPLE_COPY_PROMPT import removed — batch prompt is built inline.


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

# M5: 留白寄语按时段差异化（晨光/午后/夜色）
_REST_TEMPLATES_BY_PERIOD: Dict[str, List[str]] = {
    "上午": [
        "晨光里的{name}很安静，你在身边，一天就有了开始的样子。",
        "不用赶时间，和你慢慢醒过来，就是最好的早晨。",
    ],
    "下午": [
        "午后的{name}，阳光刚好，我们什么都不做也很好。",
        "陪你发呆，是我旅行中最珍惜的安排。",
    ],
    "晚间": [
        "夜色里的{name}，灯火温柔，牵你的手走回去就很满足。",
        "星星不多，但有你陪着，这个夜晚刚刚好。",
    ],
}


def _pick_message(act_name: str, act_type: str, period: str = "") -> str:
    """Select a template-based couple message for the given activity.

    M5: 留白类型按时段选差异化模板，其他类型按原逻辑。
    """
    import random
    if act_type == "留白" and period in _REST_TEMPLATES_BY_PERIOD:
        templates = _REST_TEMPLATES_BY_PERIOD[period]
    else:
        templates = _TEMPLATES.get(act_type, _TEMPLATES["景点"])
    template = random.choice(templates)
    return template.format(name=act_name)


def _trim_message(text: str) -> str | None:
    """Enforce the 6–25 character constraint; return None if too short."""
    if len(text) > 25:
        for sep in ("。", "，", ".", ","):
            idx = text[:25].rfind(sep)
            if idx > 8:
                text = text[:idx + 1]
                break
        else:
            text = text[:25]
    return text if len(text) >= 6 else None


def _generate_batch_llm_messages(
    destination: str,
    activities_meta: List[dict],
) -> List[str | None]:
    """P7: generate couple messages for ALL activities in one LLM call.

    Returns a list parallel to *activities_meta*: each element is the
    generated message, or None when the LLM could not produce one.
    Returns a list of Nones when no API key is configured.
    """
    n = len(activities_meta)
    if n == 0:
        return []

    fallback: List[str | None] = [None] * n
    act_list_str = json.dumps(activities_meta, ensure_ascii=False)

    prompt = (
        f"为以下 {n} 个旅行活动各生成一句情侣寄语（6-25字，温暖真挚，不油腻）。\n"
        f"目的地：{destination}\n\n"
        f"活动清单：\n{act_list_str}\n\n"
        "请严格按 JSON 数组格式返回，每项包含 id 和 message 字段：\n"
        '[{"id": 0, "message": "..."}, {"id": 1, "message": "..."}]\n'
        f"数量必须为 {n} 条，id 与活动清单中的 id 一一对应。\n\n"
        "语气指引：\n"
        "- 自然/户外：有画面感，融入自然环境元素\n"
        "- 美食：有温度，突出'分享'的快乐\n"
        "- 文化/室内：细腻安静，有'时光'感\n"
        "- 冒险：有青春感，带一点俏皮\n"
        "- 留白：慵懒温柔，按时段融入意象——上午用晨光/微风，下午用午后/阳光，晚间用夜色/灯火/星空\n"
        "- 晚间活动：浪漫静谧，有夜色和星火的意象\n"
    )

    try:
        result = call_llm(
            system_prompt=(
                "你是一个温柔细腻的情感文案写手。"
                "请严格按照 JSON 数组格式返回结果，不要添加任何前缀或后缀。"
            ),
            user_prompt=prompt,
            mock_response={},   # empty dict signals "no LLM" → all None
        )

        # Normalise: accept a raw list or a dict with a "messages"/"results" key
        items: list = (
            result
            if isinstance(result, list)
            else result.get("messages", result.get("results", []))
        )
        if not isinstance(items, list):
            return fallback

        messages: List[str | None] = [None] * n
        for item in items:
            if not isinstance(item, dict):
                continue
            idx = item.get("id", -1)
            raw = str(item.get("message", "")).strip()
            if 0 <= idx < n and raw:
                messages[idx] = _trim_message(raw)
        return messages

    except Exception:
        # P10: log instead of swallowing silently
        logger.warning(
            "Batch LLM couple-message generation failed for %d activities; "
            "falling back to template bank",
            n,
            exc_info=True,
        )
        return fallback


def add_couple_touch(state: AgentState) -> Dict[str, Any]:
    """Append a couple_note to every activity in the draft itinerary.

    P7: makes a single batch LLM call for all activities instead of one
    call per activity.  Falls back to the M1 template bank when the LLM
    is unavailable or returns incomplete results.

    Returns:
        Partial state with draft_itinerary activities enriched,
        and couple_notes list populated (first note per day).
    """
    params = state.get("parsed_params", {})
    destination = params.get("destination", "")
    weather = state.get("weather_data", {})
    draft = state.get("draft_itinerary", {})
    all_notes: List[str] = []

    weather_keys = list(weather.keys())

    # ── Phase 1: flatten all activities into a meta list ──────────
    # Each entry: (day_idx, act_ref, weather_condition)
    flat: List[tuple] = []
    activities_meta: List[dict] = []

    for day_idx, day_data in enumerate(draft.get("days", [])):
        date_key = weather_keys[day_idx] if day_idx < len(weather_keys) else ""
        w = weather.get(date_key, {})
        condition = w.get("condition", "晴")

        for act in day_data.get("activities", []):
            i = len(flat)
            flat.append((day_idx, act))
            activities_meta.append({
                "id": i,
                "name": act["name"],
                "type": act.get("type", "景点"),
                "period": act.get("period", "上午"),
                "weather": condition,
            })

    # ── Phase 2: single batch LLM call (P7) ────────────────────────
    llm_messages = _generate_batch_llm_messages(destination, activities_meta)

    # ── Phase 3: assign messages, falling back to templates ────────
    for i, (day_idx, act) in enumerate(flat):
        note = llm_messages[i] if i < len(llm_messages) else None
        if note is None:
            note = _pick_message(
                act["name"],
                act.get("type", "景点"),
                act.get("period", ""),
            )
        act["couple_note"] = note

    # ── Phase 4: collect first note per day ───────────────────────
    for day_data in draft.get("days", []):
        activities = day_data.get("activities", [])
        if activities:
            all_notes.append(activities[0].get("couple_note", ""))

    return {
        "draft_itinerary": draft,
        "couple_notes": all_notes,
        "current_phase": "add_couple_touch",
    }
