"""Conversation handler — dialog intent classification + slot extraction (P1.1).

Uses a single acall_llm call for intent + slot extraction, then applies
deterministic postprocessing (date parsing, budget normalisation) before
merging slots into Redis session storage.

When no LLM key is configured, falls back to a rule-based mock that
handles simple greetings and keyword-based slot extraction.
"""

import re
import logging
import uuid
from datetime import date, timedelta
from typing import Any

from services.llm import acall_llm
from services.session_store import session_store
from schemas.chat import ChatReply, Slots, ModifyPatch

logger = logging.getLogger("coupletrip")

# ── Required slots for planning_ready ────────────────────────────────

REQUIRED_SLOTS = ("destination", "start_date", "end_date", "budget")

# ── Prompt loading ───────────────────────────────────────────────────

def _load_prompt() -> str:
    """Load the chat intent prompt template."""
    try:
        with open("prompts/chat_intent_prompt.md", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        # Fallback: inline minimal prompt
        return (
            "你是情侣旅行规划助手。判断用户意图（greeting/question/planning_intent/"
            "planning_ready/modify_plan）并提取槽位。返回JSON。"
        )


# ── Slot postprocessing ─────────────────────────────────────────────

def postprocess_slots(raw_slots: dict, existing_slots: dict) -> dict:
    """Deterministic postprocessing of extracted slots.

    - Relative date parsing ("下周末" → concrete date)
    - Budget unit normalisation ("5千" → 5000)
    - Merge with existing slots (new values override)
    """
    processed = dict(existing_slots)

    for key, val in raw_slots.items():
        if val is None:
            continue

        if key == "budget":
            processed[key] = _normalise_budget(val)
        elif key == "start_date":
            processed[key] = _normalise_date(val, existing_slots, is_start=True)
        elif key == "end_date":
            processed[key] = _normalise_date(val, existing_slots, is_start=False)
        elif key == "preferences":
            if isinstance(val, list):
                processed[key] = val
            elif isinstance(val, str):
                processed[key] = [v.strip() for v in val.split(",")]
        elif key == "pace":
            pace_str = str(val).strip()
            if pace_str in ("轻松", "适中", "充实"):
                processed[key] = pace_str
        else:
            processed[key] = str(val).strip() if val else None

    return processed


def _normalise_budget(val: Any) -> float:
    """Convert budget expressions to a float."""
    if isinstance(val, (int, float)):
        return float(val)
    text = str(val).strip()
    # "5千" → 5000, "1万" → 10000, "1.5万" → 15000
    text = text.replace(",", "")
    match = re.match(r"^([\d.]+)\s*万$", text)
    if match:
        return float(match.group(1)) * 10000
    match = re.match(r"^([\d.]+)\s*千$", text)
    if match:
        return float(match.group(1)) * 1000
    match = re.match(r"^[\d.]+$", text)
    if match:
        return float(text)
    return 0.0


def _normalise_date(val: Any, existing: dict, is_start: bool) -> str:
    """Normalise date values; attempt relative date resolution."""
    text = str(val).strip()
    if not text or text == "null":
        return None

    # Already ISO format
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text

    # Relative dates
    today = date.today()
    if "今天" in text:
        return today.isoformat()
    if "明天" in text:
        return (today + timedelta(days=1)).isoformat()
    if "后天" in text:
        return (today + timedelta(days=2)).isoformat()
    if "下周末" in text:
        days_ahead = 6 - today.weekday()  # Saturday
        if days_ahead <= 0:
            days_ahead += 7
        return (today + timedelta(days=days_ahead)).isoformat()
    if "这周末" in text:
        days_ahead = 5 - today.weekday()  # Friday
        if days_ahead <= 0:
            days_ahead += 7
        return (today + timedelta(days=days_ahead)).isoformat()

    # "三天" → start today + 2 days end
    day_match = re.search(r"(\d+)\s*天", text)
    if day_match:
        num_days = int(day_match.group(1))
        if is_start:
            return today.isoformat()
        else:
            return (today + timedelta(days=num_days - 1)).isoformat()

    return text


# ── Incremental modification (P1.2) ──────────────────────────────────

_CN_DIGITS = {
    "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}

# Words that signal an *incremental* change rather than a fresh plan.
_MODIFY_SIGNALS = (
    "改成", "改为", "改去", "改一下", "改改", "修改", "变更",
    "调成", "调整为", "调整",
    "换成", "换到", "换个", "换一个",
    "加到", "提到", "增加到", "提升到", "变成",
    "再加", "再多", "多待", "多玩", "多住", "延长", "续住",
    "提前", "延后", "推后", "往后推",
)

# Phrases that announce a brand-new request, which outranks a bare budget mention.
_PLANNING_VERBS_RE = re.compile(r"(想去|要去|打算去|计划去|去|到|飞)\s*[^\s，。,、？?！!]+")

_DAY_SHIFT_RE = re.compile(
    r"(?:再|多|加|增加|延长|续|推后|延后|往后推|提前)\s*"
    r"([0-9]+|[一二两三四五六七八九十]+)\s*天"
)


def _cn_to_int(text: str) -> int | None:
    """Convert a small Chinese or Arabic numeral ("两" → 2, "3" → 3)."""
    text = text.strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if text in _CN_DIGITS:
        return _CN_DIGITS[text]
    if "十" in text:
        head, _, tail = text.partition("十")
        tens = _CN_DIGITS.get(head, 1) if head else 1
        ones = _CN_DIGITS.get(tail, 0) if tail else 0
        return tens * 10 + ones
    return None


def _parse_day_shift(value: Any) -> int | None:
    """Return the day delta when *value* expresses a shift, else ``None``.

    ``"+1天"`` → 1, ``"再加一天"`` → 1, ``"再多两天"`` → 2, ``"提前一天"`` → -1.
    A bare ``"3天"`` is a duration, not a shift, and returns ``None``.
    """
    text = str(value).strip()
    if not text:
        return None

    signed = re.match(r"^([+＋\-−])\s*([0-9]+)\s*天$", text)
    if signed:
        delta = int(signed.group(2))
        return -delta if signed.group(1) in "-−" else delta

    match = _DAY_SHIFT_RE.search(text)
    if not match:
        return None
    delta = _cn_to_int(match.group(1))
    if delta is None:
        return None
    return -delta if "提前" in text else delta


def _parse_day_count(value: Any) -> int | None:
    """Return the trip length in days when *value* is a bare duration."""
    text = str(value).strip()
    if _parse_day_shift(text) is not None:
        return None
    match = re.match(r"^([0-9]+|[一二两三四五六七八九十]+)\s*天$", text)
    if not match:
        return None
    return _cn_to_int(match.group(1))


def _shift_date(anchor: Any, days: int) -> str | None:
    """Shift an ISO date by *days*, or ``None`` when the anchor is not a date."""
    try:
        base = date.fromisoformat(str(anchor))
    except (TypeError, ValueError):
        return None
    return (base + timedelta(days=days)).isoformat()


def postprocess_patch(raw_patch: Any, existing_slots: dict) -> dict:
    """Normalise an incremental modify patch (P1.2).

    Beyond the normalisation ``postprocess_slots`` performs, this resolves the
    relative shifts a modification introduces — ``"再加一天"`` becomes the
    existing ``end_date`` plus one day, so the day-count boundary stays
    inclusive (2026-09-03 + 1 → 2026-09-04).
    """
    if not isinstance(raw_patch, dict):
        return {}

    patch: dict = {}
    for key, val in raw_patch.items():
        if val is None or val == "":
            continue

        if key == "budget":
            patch["budget"] = _normalise_budget(val)
        elif key in ("start_date", "end_date"):
            shift = _parse_day_shift(val)
            if shift is not None:
                anchor = existing_slots.get("end_date" if key == "end_date" else "start_date")
                shifted = _shift_date(anchor, shift) if anchor else None
                if shifted:
                    patch[key] = shifted
                continue
            count = _parse_day_count(val)
            if count is not None:
                # A bare duration re-anchors the return date on the departure date.
                start = existing_slots.get("start_date")
                shifted = _shift_date(start, count - 1) if start and count >= 1 else None
                if shifted:
                    patch[key] = shifted
                continue
            normalised = _normalise_date(val, existing_slots, is_start=(key == "start_date"))
            if normalised:
                patch[key] = normalised
        elif key == "preferences":
            if isinstance(val, list):
                cleaned = [str(v).strip() for v in val if str(v).strip()]
            else:
                cleaned = [v.strip() for v in re.split(r"[、,，和]", str(val)) if v.strip()]
            if cleaned:
                patch["preferences"] = cleaned
        elif key == "pace":
            pace_str = str(val).strip()
            if pace_str in ("轻松", "适中", "充实"):
                patch["pace"] = pace_str
        elif key in ("destination", "origin"):
            text = str(val).strip()
            if text and text != "null":
                patch[key] = text

    return patch


def _looks_like_modification(msg: str) -> bool:
    """True when *msg* asks to change an existing plan rather than start one."""
    if any(signal in msg for signal in _MODIFY_SIGNALS):
        return True
    # A bare budget restatement ("预算5000") only makes sense on an existing
    # plan; "想去三亚，预算8000元" is a fresh request and must keep planning.
    if "预算" in msg and re.search(r"[0-9]", msg):
        return not _PLANNING_VERBS_RE.search(msg)
    return False


def _extract_modify_patch(message: str, existing_slots: dict) -> dict:
    """Rule-based incremental patch extraction for the mock fallback (P1.2)."""
    msg = message.strip()
    raw: dict = {}

    # Budget — "预算加到8千" / "改成8000元" / "5000块"
    budget_match = (
        re.search(r"预算[^0-9]{0,6}?([0-9][0-9.,]*\s*[万千]?)", msg)
        or re.search(r"(?:加到|改成|提到|增加到|调整为|变成)\s*([0-9][0-9.,]*\s*[万千]?)", msg)
        or re.search(r"([0-9][0-9.,]*\s*[万千]?)\s*[元块]", msg)
    )
    if budget_match:
        raw["budget"] = budget_match.group(1)

    # Dates — a day shift wins over absolute phrasing.
    shift_match = _DAY_SHIFT_RE.search(msg) or re.search(r"([+＋\-−])\s*[0-9]+\s*天", msg)
    if shift_match:
        raw["end_date"] = shift_match.group(0)
    else:
        date_match = re.search(r"(今天|明天|后天|下周末|这周末|\d{4}-\d{2}-\d{2}|\d+\s*天)", msg)
        if date_match:
            raw["end_date"] = date_match.group(1)

    # Destination — "换成杭州" / "改成三亚"; never a budget expression.
    dest_match = re.search(r"(?:换成去|换成|改成|改为|改去|调整为)\s*([^\s，。,、？?！!]+)", msg)
    if dest_match and not re.match(r"^[0-9]", dest_match.group(1)):
        raw["destination"] = dest_match.group(1)

    # Preferences — "偏好美食、自然" / "喜欢安静"
    pref_match = re.search(r"(?:偏好|喜欢|加上)\s*([^\s，。,、？?！!]+)", msg)
    if pref_match:
        raw["preferences"] = pref_match.group(1)

    return postprocess_patch(raw, existing_slots)


def _describe_patch(patch: dict) -> str:
    """Warm one-line confirmation of what a modification changed."""
    parts = []
    if "budget" in patch:
        parts.append(f"预算调整为{patch['budget']:.0f}元")
    if "start_date" in patch:
        parts.append(f"出发日期改为{patch['start_date']}")
    if "end_date" in patch:
        parts.append(f"返程日期改为{patch['end_date']}")
    if "destination" in patch:
        parts.append(f"目的地改为{patch['destination']}")
    if "origin" in patch:
        parts.append(f"出发地改为{patch['origin']}")
    if "preferences" in patch:
        parts.append("偏好更新为" + "、".join(patch["preferences"]))
    if "pace" in patch:
        parts.append(f"节奏调整为{patch['pace']}")

    if not parts:
        return "好的～想调整哪一项？预算、日期还是目的地？"
    return "好的，" + "，".join(parts) + "。要现在重新规划吗？"


def _mock_modify(message: str, existing_slots: dict) -> dict:
    """Rule-based modification reply when no LLM key is configured."""
    patch = _extract_modify_patch(message, existing_slots)
    return {
        "intent": "modify_plan",
        "reply": _describe_patch(patch),
        "slots": {**existing_slots, **patch},
        "modify_patch": patch or None,
    }


# ── Ready check ──────────────────────────────────────────────────────

def _check_ready(slots: dict) -> bool:
    """Return True when all required slots are present."""
    return all(slots.get(k) for k in REQUIRED_SLOTS)


def _build_plan_request(slots: dict) -> dict:
    """Convert slot dict to POST /api/plan request body."""
    return {
        "origin": slots.get("origin") or "未指定",
        "destination": slots["destination"],
        "start_date": slots["start_date"],
        "end_date": slots["end_date"],
        "budget": float(slots["budget"]),
        "preferences": slots.get("preferences") or ["浪漫", "美食"],
        "pace": slots.get("pace") or "轻松",
    }


# ── Mock fallback ────────────────────────────────────────────────────

def _mock_handle(message: str, existing_slots: dict) -> dict:
    """Rule-based fallback when no LLM key is configured."""
    msg = message.lower().strip()

    # P1.2: a modification of an already-complete plan outranks every other
    # rule — including a greeting prefix ("你好，预算加到8千").
    if _check_ready(existing_slots) and _looks_like_modification(msg):
        return _mock_modify(message, existing_slots)

    # Greeting
    if any(w in msg for w in ("你好", "hi", "hello", "嗨", "哈喽")):
        return {
            "intent": "greeting",
            "reply": "嗨～想去哪里度个假？说说你的旅行想法吧。",
            "slots": existing_slots,
        }

    # Question
    if any(w in msg for w in ("什么", "怎么", "哪儿", "哪", "？", "?")) and not any(
        w in msg for w in ("想去", "规划", "安排", "行程")
    ):
        return {
            "intent": "question",
            "reply": "好问题～不过我更擅长帮你规划行程，要不说说你想去哪？",
            "slots": existing_slots,
        }

    # Extract destination
    new_slots = dict(existing_slots)
    dest_match = re.search(r"(想去|去|到|飞)\s*([^\s，。,]+)", msg)
    if dest_match:
        new_slots["destination"] = dest_match.group(2)

    # Extract budget
    budget_match = re.search(r"(\d[\d.]*万?千?)\s*[元块]", msg) or re.search(r"预算\s*(\d[\d.]*万?千?)", msg)
    if budget_match:
        new_slots["budget"] = _normalise_budget(budget_match.group(1))

    # Extract dates
    if "下周末" in msg:
        d = _normalise_date("下周末", {}, True)
        new_slots["start_date"] = d
        new_slots["end_date"] = (date.fromisoformat(d) + timedelta(days=1)).isoformat()
    day_match = re.search(r"(\d+)\s*天", msg)
    if day_match:
        num = int(day_match.group(1))
        new_slots["start_date"] = date.today().isoformat()
        new_slots["end_date"] = (date.today() + timedelta(days=num - 1)).isoformat()

    ready = _check_ready(new_slots)
    if ready:
        return {
            "intent": "planning_ready",
            "reply": f"好的，{new_slots['destination']}行程马上为你安排～",
            "slots": new_slots,
        }

    missing = [k for k in REQUIRED_SLOTS if not new_slots.get(k)]
    hint_map = {"destination": "目的地", "start_date": "出发日期", "end_date": "返程日期", "budget": "预算"}
    hints = "、".join(hint_map.get(k, k) for k in missing)
    return {
        "intent": "planning_intent",
        "reply": f"记下了～还差{hints}，一起补全吧？",
        "slots": new_slots,
    }


# ── Main handler ─────────────────────────────────────────────────────

async def handle_chat(message: str, session_id: str | None) -> ChatReply:
    """Process a chat message and return a structured reply.

    Args:
        message: User's input text.
        session_id: Existing session ID, or None for new sessions.

    Returns:
        ChatReply with intent, reply text, merged slots, and optional plan_request.
    """
    # Generate session_id if not provided
    sid = session_id or uuid.uuid4().hex

    # Load existing slots from Redis
    existing_slots = await session_store.get_slots(sid)

    # Call LLM for intent + slot extraction
    system_prompt = _load_prompt()
    user_prompt = f"已有槽位: {existing_slots}\n用户消息: {message}"

    result = None
    try:
        result = await acall_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            mock_response=None,  # signal: use _mock_handle instead
        )
    except Exception as exc:
        # acall_llm re-raises when mock_response is None; degrade to the
        # rule-based handler so a transient LLM failure never 500s.
        logger.warning("Chat LLM call failed, falling back to mock: %s", exc)

    if result is None or "error" in result:
        # Mock fallback
        mock_result = _mock_handle(message, existing_slots)
        raw_slots = mock_result["slots"]
        intent = mock_result["intent"]
        reply = mock_result["reply"]
        raw_modify_patch = mock_result.get("modify_patch")
    else:
        raw_slots = result.get("slots", {})
        intent = result.get("intent", "planning_intent")
        reply = result.get("reply", "让我想想...")
        raw_modify_patch = result.get("modify_patch")

    # Postprocess slots, then fold the modify patch on top (P1.2)
    processed_slots = postprocess_slots(raw_slots, existing_slots)

    modify_patch = None
    if intent == "modify_plan":
        patch_values = postprocess_patch(raw_modify_patch, processed_slots)
        if patch_values:
            processed_slots = {**processed_slots, **patch_values}
            modify_patch = ModifyPatch(**patch_values)

    # Merge into Redis session
    await session_store.merge_slots(sid, processed_slots)
    await session_store.add_message(sid, "user", message)
    await session_store.add_message(sid, "assistant", reply)

    # A modification never auto-plans: ready is reset so the user confirms
    # the new request explicitly (the frontend re-arms its plan button).
    ready = _check_ready(processed_slots) and intent in ("planning_ready", "planning_intent")

    # Build plan_request if ready
    plan_request = _build_plan_request(processed_slots) if ready else None

    return ChatReply(
        session_id=sid,
        reply=reply,
        intent=intent,
        slots=Slots(**{k: v for k, v in processed_slots.items() if k in Slots.model_fields}),
        ready=ready,
        plan_request=plan_request,
        modify_patch=modify_patch,
    )
