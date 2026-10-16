"""Conversation memory layers (V3/P2).

L0 working memory lives in ``services.conversation_store`` (the transcript
window that goes into the prompt). This module holds the layers on top:

  L1  rolling summary  — compresses the turns that slid out of the window
  L2  durable profile  — facts that outlive a session: origin, pace, budget
                         range, preferences, things to avoid
  L3  episodic recall  — past trips and per-activity thumbs feedback

L1–L3 are deliberately built on **structured storage + SQL recall**, not
embeddings: the V2 decision to skip pgvector was about vector search, not about
long-term memory, and conflating the two is what left the agent with no memory
at all. Everything here is a pure function or a thin LLM call, so prompt
assembly and merge rules are testable without a database.
"""

import json
import logging
import re
from typing import Optional

from services.llm import acall_llm_text

logger = logging.getLogger("coupletrip")

# ── Memory budget (T2.4) ─────────────────────────────────────────────

# Turns ("轮" = one user+assistant exchange) replayed verbatim.
HISTORY_EXCHANGES = 10
HISTORY_MESSAGES = HISTORY_EXCHANGES * 2

# Summarise only once real overflow exists, and only when at least this many
# new messages have fallen out — otherwise every single turn would pay for an
# extra LLM call.
SUMMARY_MIN_NEW_MESSAGES = 4

MAX_SUMMARY_CHARS = 1200
MAX_CONFLICT_VALUES = 3
MAX_TRIPS_IN_PROMPT = 5
MAX_FEEDBACK_IN_PROMPT = 5

# "我不吃辣" / "她忌口海鲜" / "对花生过敏" / "过敏于芒果"
# Two orders: the item usually follows the keyword, but "对X过敏" puts it first.
_AVOID_ITEM = r"([^\s，。,、；;！!？?]{1,6})"
_AVOID_PATTERNS = (
    re.compile(rf"(?:不吃|忌口|讨厌|过敏(?:于)?)\s*{_AVOID_ITEM}"),
    re.compile(rf"对\s*{_AVOID_ITEM}?\s*过敏"),
)

SUMMARY_SYSTEM_PROMPT = """你在压缩一段情侣旅行规划对话的历史，供后续对话继续使用。

要求：
- 保留仍然有效的事实：目的地、日期、预算、人数、偏好、节奏、忌口、已确认或已否决的方案。
- 保留尚未解决的问题：还缺哪些信息、用户上一次在问什么。
- 丢弃寒暄、重复与语气词。
- 用第三人称中文要点陈述，最多 200 字。
- 如果给了"已有摘要"，把新增内容并入，不要丢失旧摘要里仍然有效的信息。
- 只输出摘要正文：不要标题、不要 JSON、不要 Markdown 代码块。"""


# ── L2: durable profile ──────────────────────────────────────────────

def profile_updates_from(slots: dict, message: str = "") -> dict:
    """Deterministically derive durable facts from one turn.

    Only *durable* values are kept: a per-trip budget becomes a budget
    *range*, and only the slots that describe the travellers rather than one
    specific trip (origin / pace / preferences) are promoted.
    """
    updates: dict = {}
    slots = slots or {}

    origin = (slots.get("origin") or "").strip()
    if origin and origin not in ("未指定",):
        updates["origin"] = origin

    pace = slots.get("pace")
    if pace in ("轻松", "适中", "充实"):
        updates["pace"] = pace

    preferences = [p for p in (slots.get("preferences") or []) if p]
    if preferences:
        updates["preferences"] = preferences

    budget = slots.get("budget")
    if isinstance(budget, (int, float)) and budget > 0:
        updates["budget"] = float(budget)

    avoid: list[str] = []
    for pattern in _AVOID_PATTERNS:
        avoid.extend(pattern.findall(message or ""))
    if avoid:
        updates["avoid"] = list(dict.fromkeys(avoid))

    return updates


def merge_profile(existing: Optional[dict], updates: Optional[dict]) -> dict:
    """Merge L2 updates, never silently dropping a replaced value.

    Growth-only by design: a scalar that gets overwritten keeps its previous
    value under ``conflicts``, so the prompt can say "出发地：上海（此前提到过：
    北京）" instead of erasing what the user said earlier. Collections union.
    """
    profile = json.loads(json.dumps(existing or {}))
    conflicts = profile.setdefault("conflicts", {})

    for key, value in (updates or {}).items():
        if value is None or value == "" or value == []:
            continue

        if key in ("preferences", "avoid"):
            current = profile.get(key) or []
            incoming = value if isinstance(value, list) else [value]
            profile[key] = [v for v in dict.fromkeys([*current, *incoming]) if v]
        elif key == "budget":
            low, high = (profile.get("budget_range") or [None, None])[:2]
            low = value if low is None else min(low, value)
            high = value if high is None else max(high, value)
            profile["budget_range"] = [low, high]
        else:
            previous = profile.get(key)
            if previous and previous != value:
                seen = [v for v in conflicts.get(key, []) if v != previous]
                conflicts[key] = [previous, *seen][:MAX_CONFLICT_VALUES]
            profile[key] = value

    if not conflicts:
        profile.pop("conflicts", None)
    return profile


def render_profile(profile: Optional[dict]) -> str:
    """Render L2 as a system-prompt section (empty string when nothing known)."""
    if not profile:
        return ""

    conflicts = profile.get("conflicts") or {}
    lines = []

    if profile.get("origin"):
        line = f"- 出发地：{profile['origin']}"
        previous = conflicts.get("origin")
        if previous:
            line += f"（此前提到过：{'、'.join(str(v) for v in previous)}）"
        lines.append(line)

    if profile.get("pace"):
        line = f"- 节奏偏好：{profile['pace']}"
        previous = conflicts.get("pace")
        if previous:
            line += f"（此前提到过：{'、'.join(str(v) for v in previous)}）"
        lines.append(line)

    budget_range = profile.get("budget_range")
    if budget_range and any(v is not None for v in budget_range):
        low, high = budget_range[0], budget_range[1]
        if low is not None and high is not None and low != high:
            lines.append(f"- 预算区间：约 {low:.0f}–{high:.0f} 元")
        else:
            lines.append(f"- 预算：约 {(low or high):.0f} 元")

    if profile.get("preferences"):
        lines.append("- 偏好：" + "、".join(profile["preferences"]))

    if profile.get("avoid"):
        lines.append("- 需要避开：" + "、".join(profile["avoid"]))

    if not lines:
        return ""
    return "## 已知用户偏好（跨会话记忆）\n" + "\n".join(lines)


# ── L3: episodic recall ──────────────────────────────────────────────

def render_past_trips(
    plans: Optional[list[dict]],
    feedback: Optional[list[dict]],
) -> str:
    """Render L3 as a system-prompt section (empty string when nothing known)."""
    sections = []

    trips = [p for p in (plans or []) if p.get("destination")]
    if trips:
        lines = []
        for plan in trips[:MAX_TRIPS_IN_PROMPT]:
            dates = "~".join(
                str(v) for v in (plan.get("start_date"), plan.get("end_date")) if v
            )
            status = "已完成" if plan.get("status") == "completed" else "生成中"
            suffix = f" {dates}" if dates else ""
            lines.append(f"- {plan['destination']}{suffix}（{status}）")
        sections.append("## 过往行程（情节记忆）\n" + "\n".join(lines))

    liked = [f for f in (feedback or []) if f.get("up")]
    disliked = [f for f in (feedback or []) if f.get("down")]
    if liked or disliked:
        lines = []
        if liked:
            lines.append(
                "- 用户点赞过的活动："
                + "、".join(f"{f['activity_name']}（{f['up']}）" for f in liked[:MAX_FEEDBACK_IN_PROMPT])
            )
        if disliked:
            lines.append(
                "- 用户点踩过的活动："
                + "、".join(f"{f['activity_name']}（{f['down']}）" for f in disliked[:MAX_FEEDBACK_IN_PROMPT])
            )
        sections.append("## 活动反馈（情节记忆）\n" + "\n".join(lines))

    return "\n\n".join(sections)


# ── L1: rolling summary ──────────────────────────────────────────────

def render_summary(summary: Optional[str]) -> str:
    """Render L1 as a system-prompt section."""
    if not summary or not summary.strip():
        return ""
    return "## 早前对话摘要（已滑出窗口的部分）\n" + summary.strip()


def should_summarise(total_messages: int, covered_messages: int) -> bool:
    """Decide whether L1 needs an update (pure, so the rule is testable).

    ``overflow`` is how many messages can never reappear in the window again;
    ``covered`` is how many the stored summary already accounts for.
    """
    overflow = total_messages - HISTORY_MESSAGES
    if overflow <= 0:
        return False
    return (overflow - covered_messages) >= SUMMARY_MIN_NEW_MESSAGES


def transcript_text(messages: list[dict]) -> str:
    """Render stored turns as plain text for the compression prompt."""
    lines = []
    for message in messages:
        speaker = "用户" if message.get("role") == "user" else "助手"
        content = str(message.get("content") or "").strip()
        if content:
            lines.append(f"{speaker}：{content}")
    return "\n".join(lines)


async def compress_summary(
    previous_summary: Optional[str],
    overflow_messages: list[dict],
) -> str:
    """Merge newly overflowed turns into the rolling summary (L1).

    Returns "" when no API key is configured, in which case the caller keeps
    the previous summary rather than losing it.
    """
    if not overflow_messages:
        return ""

    user_prompt = (
        f"已有摘要：{previous_summary or '（无）'}\n\n"
        f"新增对话：\n{transcript_text(overflow_messages)}"
    )
    try:
        text = await acall_llm_text(
            system_prompt=SUMMARY_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
    except Exception as exc:
        logger.warning("L1 summary compression failed, keeping previous summary: %s", exc)
        return ""

    return (text or "").strip()[:MAX_SUMMARY_CHARS]


# ── Prompt assembly (T2.4) ───────────────────────────────────────────

def memory_context(
    profile: Optional[dict] = None,
    past_trips: Optional[str] = None,
    summary: Optional[str] = None,
) -> str:
    """Assemble the memory sections in a fixed order.

    Order matters and is pinned by tests:
    L2 profile → L3 past trips → L1 summary → (L0 transcript follows as real
    messages). Most durable facts first, most volatile last.
    """
    sections = [
        render_profile(profile),
        past_trips or "",
        render_summary(summary),
    ]
    return "\n\n".join(s for s in sections if s)


def compose_system_prompt(base: str, context: str) -> str:
    """Attach the memory context to a base system prompt."""
    return f"{base}\n\n{context}" if context else base
