"""Conversation handler — dialog intent classification + slot extraction (P1.1).

Two LLM calls at most, on purpose:

  1. **Always** — intent + slot extraction, as structured JSON, carrying the
     recent transcript (L0 memory) so multi-turn references resolve.
  2. **Only for conversational intents** (``question`` / ``greeting``) — a
     free-form answer via :func:`acall_llm_text`.  Forcing these through the
     JSON contract is exactly why the agent used to reply "好问题～不过我更擅长
     帮你规划行程" instead of answering.  Planning intents instead reuse a
     deterministic confirmation (more reliable *and* cheaper than an extra
     generation).

Memory is layered (see ``agents.memory``): L0 recent transcript, L1 rolling
summary of turns that slid out of the window, L2 durable cross-session profile,
L3 past trips and activity feedback. Sessions, slots and the transcript live in
PostgreSQL (V3/P1) rather than a 30-minute Redis TTL, so a conversation survives
refreshes, restarts and days. When no LLM key is configured,
:func:`_mock_handle` keeps everything working with rule-based fallbacks.
"""

import asyncio
import re
import logging
from datetime import date, timedelta
from typing import Any

from agents import memory
from services.llm import acall_llm, acall_llm_text
from services.conversation_store import conversation_store, generate_session_id
from services.storage import plan_store
from schemas.chat import ChatReply, Slots, ModifyPatch

logger = logging.getLogger("coupletrip")

# Intents whose reply must be genuinely generated rather than templated.
CONVERSATIONAL_INTENTS = ("question", "greeting")

# Session titles come from the first substantive user message.
TITLE_MAX_CHARS = 20
_UNTITLED_INTENTS = ("greeting", "question")

# ── Required slots for planning_ready ────────────────────────────────

REQUIRED_SLOTS = ("destination", "start_date", "end_date", "budget")

# ── Prompt loading ───────────────────────────────────────────────────

def _read_prompt(path: str, fallback: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return fallback


def _load_prompt() -> str:
    """Load the chat intent prompt template."""
    return _read_prompt(
        "prompts/chat_intent_prompt.md",
        # Fallback: inline minimal prompt
        "你是情侣旅行规划助手。判断用户意图（greeting/question/planning_intent/"
        "planning_ready/modify_plan）并提取槽位。返回JSON。",
    )


def _load_reply_prompt() -> str:
    """Load the free-form reply prompt (used for question / greeting)."""
    return _read_prompt(
        "prompts/chat_reply_prompt.md",
        "你是情侣旅行助手。用中文简洁温暖地回答用户，120字以内，不要输出JSON。"
        "结合历史对话，不要复述用户的话，不要编造具体票价与营业时间。",
    )


# ── Slot postprocessing ─────────────────────────────────────────────

def _is_empty_slot_value(val: Any) -> bool:
    """True when a raw slot value carries no information.

    The LLM is told to emit ``null`` for unmentioned fields, but in practice it
    also returns ``""`` or the string ``"null"``. All three must be treated as
    "not mentioned" — otherwise a follow-up turn ("想去大理") would clobber the
    dates and budget collected in earlier turns with nulls.
    """
    if val is None:
        return True
    if isinstance(val, str):
        return not val.strip() or val.strip().lower() == "null"
    return False


def postprocess_slots(raw_slots: dict, existing_slots: dict) -> dict:
    """Deterministic postprocessing of extracted slots.

    - Relative date parsing ("下周末" → concrete date)
    - Budget unit normalisation ("5千" → 5000)
    - Merge with existing slots (new values override; empty/None never erase)
    """
    processed = dict(existing_slots)

    for key, val in raw_slots.items():
        if _is_empty_slot_value(val):
            continue  # never clobber an already-collected slot with "null"/""/None

        if key == "budget":
            normalised = _normalise_budget(val)
            if normalised > 0:
                processed[key] = normalised
        elif key == "start_date":
            normalised = _normalise_date(val, existing_slots, is_start=True)
            if normalised:
                processed[key] = normalised
        elif key == "end_date":
            normalised = _normalise_date(val, existing_slots, is_start=False)
            if normalised:
                processed[key] = normalised
        elif key == "preferences":
            if isinstance(val, list):
                cleaned = [v for v in val if str(v).strip()]
                if cleaned:
                    processed[key] = cleaned
            elif isinstance(val, str):
                cleaned = [v.strip() for v in val.split(",") if v.strip()]
                if cleaned:
                    processed[key] = cleaned
        elif key == "pace":
            pace_str = str(val).strip()
            if pace_str in ("轻松", "适中", "充实"):
                processed[key] = pace_str
        else:
            text = str(val).strip()
            if text and text != "null":
                processed[key] = text

    return processed


def _normalise_budget(val: Any) -> float:
    """Convert budget expressions to a float.

    Understands Arabic and Chinese numerals with a unit: ``"5千"`` → 5000,
    ``"1.5万"`` → 15000, ``"五千"`` → 5000, ``"一万二"`` → 12000.
    """
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

    # Chinese numerals: "五千" / "一万" / "一万二" / "三百"
    cn = re.match(r"^([一二两三四五六七八九十]+)\s*([千万百])?\s*([一二两三四五六七八九])?$", text)
    if cn:
        base = _cn_to_int(cn.group(1))
        if base is not None:
            unit = cn.group(2)
            tail = _cn_to_int(cn.group(3)) if cn.group(3) else 0
            if unit == "万":
                # "一万二" means 12000, i.e. the tail is a fraction of the unit
                return float(base * 10000 + (tail or 0) * 1000)
            if unit == "千":
                return float(base * 1000 + (tail or 0) * 100)
            if unit == "百":
                return float(base * 100 + (tail or 0) * 10)
            return float(base)
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
    day_match = _DAY_COUNT_RE.search(text)
    if day_match:
        num_days = _cn_to_int(day_match.group(1))
        if not num_days:
            return text
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

# A budget amount, written with Arabic or Chinese numerals: "5000", "5千",
# "1.5万", "五千", "一万", "一万二", "八千". Shared by the fresh-request path and
# the incremental-modify path so both understand the same phrasings.
#
# The Chinese branch requires a magnitude unit on purpose: without it "改成三亚"
# parses 三 as a budget of 3 yuan, silently overwriting the user's real budget
# with nonsense whenever a destination happens to contain a numeral.
_BUDGET_AMOUNT = (
    r"(?:[0-9][0-9.,]*\s*[万千]?"
    r"|[一二两三四五六七八九十]+\s*[千万百][一二两三四五六七八九]?)"
)

# A trip length as users actually write it: "3天" but also "三天" / "七天".
# Matching only \d+ left "想去大理玩三天" stuck at "还差出发日期、返程日期" forever,
# so the chat could never reach the point of offering to plan.
_DAY_COUNT_RE = re.compile(r"([0-9]+|[一二两三四五六七八九十]+)\s*天")

# Explicit dates: "2026-09-01 到 2026-09-03" or "9月1日到9月3日".
_ISO_DATE_RE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_CN_DATE_RE = re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]")

# Trailing filler a destination capture drags along. Applied in two passes
# because the duration and the verb sit next to each other: "大理玩三天" -> the
# duration goes first ("大理玩"), then the verb ("大理").
_DEST_TRAILING_VERB_RE = re.compile(r"(?:玩|呆|待|住|游|耍|旅行|旅游|逛逛|看看|溜达)+$")


def _clean_destination(raw: str) -> str:
    """Strip the duration/verb tail a greedy destination match picked up.

    ``"大理玩三天"`` → ``"大理"``. Without this the itinerary, the plan title and
    the L2 profile all inherit the noise.
    """
    cleaned = _DAY_COUNT_RE.sub("", raw).strip()
    cleaned = _DEST_TRAILING_VERB_RE.sub("", cleaned).strip()
    return cleaned or raw


def _extract_date_range(message: str) -> tuple[str, str] | None:
    """Read an explicit start/end pair out of *message*, if one is present.

    Handles ``2026-09-01 到 2026-09-03`` and ``9月1日到9月3日``. A bare month/day
    pair takes the current year, rolling to next year when it is already past,
    which is what "9月1日" means in practice for a trip planner.
    """
    iso = _ISO_DATE_RE.findall(message)
    if len(iso) >= 2:
        return f"{iso[0][0]}-{int(iso[0][1]):02d}-{int(iso[0][2]):02d}", f"{iso[1][0]}-{int(iso[1][1]):02d}-{int(iso[1][2]):02d}"

    cn = _CN_DATE_RE.findall(message)
    if len(cn) >= 2:
        today = date.today()
        year = today.year
        try:
            first = date(year, int(cn[0][0]), int(cn[0][1]))
            second = date(year, int(cn[1][0]), int(cn[1][1]))
            if second < first:  # crosses new year, e.g. 12月28日到1月3日
                second = second.replace(year=year + 1)
            if second < today:  # the whole range is in the past -> next year
                first = first.replace(year=year + 1)
                second = second.replace(year=year + 1)
            return first.isoformat(), second.isoformat()
        except ValueError:
            return None

    return None


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
    # A bare budget restatement ("预算5000" / "预算五千") only makes sense on an
    # existing plan; "想去三亚，预算8000元" is a fresh request and must keep planning.
    # The Chinese branch requires an actual magnitude unit so that an incidental
    # "一" (as in "一起") is not mistaken for an amount.
    if "预算" in msg and re.search(r"[0-9]|[一二两三四五六七八九十]+\s*[千万百]", msg):
        return not _PLANNING_VERBS_RE.search(msg)
    return False


def _extract_modify_patch(message: str, existing_slots: dict) -> dict:
    """Rule-based incremental patch extraction for the mock fallback (P1.2)."""
    msg = message.strip()
    raw: dict = {}

    # Budget — "预算加到8千" / "改成8000元" / "5000块" / "预算加到八千"
    budget_match = (
        re.search(rf"预算[^0-9]{{0,6}}?({_BUDGET_AMOUNT})", msg)
        or re.search(rf"(?:加到|改成|提到|增加到|调整为|变成)\s*({_BUDGET_AMOUNT})", msg)
        or re.search(rf"({_BUDGET_AMOUNT})\s*[元块]", msg)
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
        new_slots["destination"] = _clean_destination(dest_match.group(2))

    # Extract origin — "从上海出发" / "从北京去大理". Feeds both the slots and the
    # durable L2 profile, so the rule-based path needs it too.
    origin_match = re.search(r"(?:从|由)\s*([^\s，。,、]{2,6}?)\s*(?:出发|去|到|飞)", msg)
    if origin_match:
        new_slots["origin"] = origin_match.group(1)

    # Extract budget
    budget_match = re.search(rf"({_BUDGET_AMOUNT})\s*[元块]", msg) or re.search(
        rf"预算\s*({_BUDGET_AMOUNT})", msg
    )
    if budget_match:
        new_slots["budget"] = _normalise_budget(budget_match.group(1))

    # Extract dates
    if "下周末" in msg:
        d = _normalise_date("下周末", {}, True)
        new_slots["start_date"] = d
        new_slots["end_date"] = (date.fromisoformat(d) + timedelta(days=1)).isoformat()
    explicit = _extract_date_range(msg)
    if explicit:
        new_slots["start_date"], new_slots["end_date"] = explicit
    else:
        day_match = _DAY_COUNT_RE.search(msg)
        if day_match:
            num = _cn_to_int(day_match.group(1))
            if num:
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

def _make_title(message: str) -> str:
    """Derive a session title from the first substantive user message."""
    cleaned = re.sub(r"\s+", " ", message).strip()
    return cleaned[:TITLE_MAX_CHARS] or "新对话"


def _planning_reply(intent: str, slots: dict) -> str:
    """Deterministic confirmation for planning intents.

    Planning replies restate known facts (what changed, what is still
    missing), so a template is both more reliable and cheaper than an extra
    generation. Only used when the model returned no reply text at all.
    """
    if intent == "planning_ready":
        return f"好的，{slots.get('destination', '目的地')}的行程马上为你安排～"
    if intent == "modify_plan":
        return "好的，已经按你说的调整了。要现在重新规划吗？"
    missing = [k for k in REQUIRED_SLOTS if not slots.get(k)]
    hint_map = {
        "destination": "目的地",
        "start_date": "出发日期",
        "end_date": "返程日期",
        "budget": "预算",
    }
    hints = "、".join(hint_map.get(k, k) for k in missing)
    if not hints:
        return "好呀，那我们接着聊～"
    return f"记下了～还差{hints}，一起补全吧？"


async def load_episodic_recall() -> dict:
    """L3: recent trips and per-activity thumbs feedback.

    Both live in the tables built earlier (``plans``, ``plan_feedback``) — this
    is the first time the feedback table is read on the live path; until now it
    was only consumed by the offline recompute script.
    """
    try:
        trips = await asyncio.to_thread(plan_store.list, 20, 0)
        feedback = await asyncio.to_thread(plan_store.list_feedback)
    except Exception as exc:
        logger.warning("L3 recall failed, continuing without it: %s", exc)
        return {"trips": [], "feedback": []}
    return {"trips": trips or [], "feedback": feedback or []}


async def _maybe_update_summary(session_id: str) -> None:
    """L1: fold turns that fell out of the window into the rolling summary.

    Best-effort: a failure here must never cost the user their reply.
    """
    try:
        session = await conversation_store.get_session(session_id)
        if not session:
            return

        total = session.get("message_count", 0)
        covered = session.get("summary_message_count", 0)
        if not memory.should_summarise(total, covered):
            return

        overflow = total - memory.HISTORY_MESSAGES
        newly_overflowed = await conversation_store.get_messages(
            session_id, limit=overflow - covered, offset=covered
        )
        summary = await memory.compress_summary(session.get("summary"), newly_overflowed)
        if summary:
            await conversation_store.set_summary(
                session_id, summary, covered_messages=overflow
            )
    except Exception as exc:
        logger.warning("L1 summary update failed (conversation continues): %s", exc)


async def handle_chat(
    message: str,
    session_id: str | None = None,
    client_id: str | None = None,
    message_id: str | None = None,
) -> ChatReply:
    """Process a chat message and return a structured reply.

    Args:
        message:    User's input text.
        session_id: Existing session ID, or None for a new session.
        client_id:  Stable per-browser id, used to scope sessions (L2 profiles
                    hang off the same key).
        message_id: Client-generated turn id; makes the append idempotent so a
                    retried request cannot duplicate the user's message.

    Returns:
        ChatReply with intent, reply text, merged slots, and optional plan_request.
    """
    sid = session_id or generate_session_id()

    # Make sure the session row exists before anything references it, so a
    # session_id from a stale local pointer self-heals instead of failing the
    # foreign key on the first message.
    await conversation_store.ensure_session(sid, client_id)

    session = await conversation_store.get_session(sid) or {}
    existing_slots = session.get("slots") or {}

    # L0 memory: the transcript *before* this turn. Loaded before the append
    # below so the current message is not duplicated in the prompt.
    history = await conversation_store.get_recent_messages(
        sid, limit=memory.HISTORY_MESSAGES
    )

    # L2 + L3 + L1, assembled most-durable-first (order pinned by tests).
    profile = await conversation_store.get_profile(client_id) if client_id else {}
    episodic = await load_episodic_recall()
    context = memory.memory_context(
        profile=profile,
        past_trips=memory.render_past_trips(episodic["trips"], episodic["feedback"]),
        summary=session.get("summary"),
    )

    # Persist the user turn before calling the LLM (recovery matrix #5): if the
    # browser dies mid-request, their message is not lost.
    user_message_id = message_id or generate_session_id()
    await conversation_store.append_message(
        sid, "user", message, message_id=user_message_id
    )

    # ── Call 1: intent + slots, with memory ──────────────────────────
    user_prompt = f"已有槽位: {existing_slots}\n用户消息: {message}"

    result = None
    try:
        result = await acall_llm(
            system_prompt=memory.compose_system_prompt(_load_prompt(), context),
            user_prompt=user_prompt,
            mock_response=None,  # signal: use _mock_handle instead
            history=history,
        )
    except Exception as exc:
        # acall_llm re-raises when mock_response is None; degrade to the
        # rule-based handler so a transient LLM failure never 500s.
        logger.warning("Chat LLM call failed, falling back to mock: %s", exc)

    if result is None or "error" in result:
        mock_result = _mock_handle(message, existing_slots)
        raw_slots = mock_result["slots"]
        intent = mock_result["intent"]
        fallback_reply = mock_result["reply"]
        raw_modify_patch = mock_result.get("modify_patch")
    else:
        raw_slots = result.get("slots", {})
        intent = result.get("intent", "planning_intent")
        fallback_reply = result.get("reply") or ""
        raw_modify_patch = result.get("modify_patch")

    # ── Slots: postprocess, then fold the modify patch on top (P1.2) ──
    processed_slots = postprocess_slots(raw_slots, existing_slots)

    modify_patch = None
    if intent == "modify_plan":
        patch_values = postprocess_patch(raw_modify_patch, processed_slots)
        if patch_values:
            processed_slots = {**processed_slots, **patch_values}
            modify_patch = ModifyPatch(**patch_values)

    await conversation_store.update_slots(sid, processed_slots)

    # Title the session from the first substantive message (a greeting or a
    # one-off question is not a useful label for the conversation list).
    if intent not in _UNTITLED_INTENTS:
        await conversation_store.set_title_if_empty(sid, _make_title(message))

    # A modification never auto-plans: ready is reset so the user confirms the
    # new request explicitly (the frontend re-arms its plan button).
    ready = _check_ready(processed_slots) and intent in ("planning_ready", "planning_intent")
    plan_request = _build_plan_request(processed_slots) if ready else None
    if plan_request is not None:
        await conversation_store.set_plan_request(sid, plan_request)

    # ── Reply ────────────────────────────────────────────────────────
    reply = fallback_reply
    if intent in CONVERSATIONAL_INTENTS:
        # Call 2: a real answer instead of a deflection. Returns "" when no
        # API key is configured, in which case the rule-based reply stands.
        try:
            generated = await acall_llm_text(
                system_prompt=memory.compose_system_prompt(_load_reply_prompt(), context),
                user_prompt=message,
                history=history,
            )
        except Exception as exc:
            logger.warning("Chat reply generation failed, using fallback: %s", exc)
            generated = ""

        reply = generated or fallback_reply or _planning_reply(intent, processed_slots)
    elif not reply:
        reply = _planning_reply(intent, processed_slots)

    # Key the reply off the user turn so a *whole* turn is idempotent: a replay
    # of a turn that already completed skips both rows instead of appending a
    # second assistant reply (recovery #6).
    await conversation_store.append_message(
        sid, "assistant", reply, message_id=f"{user_message_id}:reply"
    )

    # ── L2: promote durable facts learned this turn ──────────────────
    # Read-modify-write against the profile loaded above. A concurrent write
    # from another tab could lose an update; acceptable for a single-user app
    # with no auth, and the merge is commutative for the collection fields.
    if client_id:
        updates = memory.profile_updates_from(processed_slots, message)
        if updates:
            await conversation_store.merge_profile(
                client_id, memory.merge_profile(profile, updates)
            )

    # ── L1: fold newly overflowed turns into the rolling summary ─────
    await _maybe_update_summary(sid)

    return ChatReply(
        session_id=sid,
        reply=reply,
        intent=intent,
        slots=Slots(**{k: v for k, v in processed_slots.items() if k in Slots.model_fields}),
        ready=ready,
        plan_request=plan_request,
        modify_patch=modify_patch,
    )
