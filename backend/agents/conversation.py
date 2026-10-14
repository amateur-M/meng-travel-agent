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

    result = await acall_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        mock_response=None,  # signal: use _mock_handle instead
    )

    if result is None or "error" in result:
        # Mock fallback
        mock_result = _mock_handle(message, existing_slots)
        raw_slots = mock_result["slots"]
        intent = mock_result["intent"]
        reply = mock_result["reply"]
        raw_modify_patch = None
    else:
        raw_slots = result.get("slots", {})
        intent = result.get("intent", "planning_intent")
        reply = result.get("reply", "让我想想...")
        raw_modify_patch = result.get("modify_patch")

    # Postprocess slots
    processed_slots = postprocess_slots(raw_slots, existing_slots)

    # Merge into Redis session
    await session_store.merge_slots(sid, processed_slots)
    await session_store.add_message(sid, "user", message)
    await session_store.add_message(sid, "assistant", reply)

    # Check ready
    ready = _check_ready(processed_slots) and intent in ("planning_ready", "planning_intent")

    # Build plan_request if ready
    plan_request = _build_plan_request(processed_slots) if ready else None

    # Build modify_patch if applicable (P1.2)
    modify_patch = None
    if intent == "modify_plan" and raw_modify_patch:
        modify_patch = ModifyPatch(**raw_modify_patch) if isinstance(raw_modify_patch, dict) else None

    return ChatReply(
        session_id=sid,
        reply=reply,
        intent=intent,
        slots=Slots(**{k: v for k, v in processed_slots.items() if k in Slots.model_fields}),
        ready=ready,
        plan_request=plan_request,
        modify_patch=modify_patch,
    )
