"""Prompt templates for the travel planning agent.

Templates are loaded from .md files for readability and version control.
The module also exposes ``fill_prompt`` — a shared placeholder-substitution
helper previously duplicated across three node modules (tidy phase).
"""

import os

_PROMPTS_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_md(filename: str) -> str:
    """Load a markdown prompt template file, stripping metadata."""
    path = os.path.join(_PROMPTS_DIR, filename)
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # Strip YAML frontmatter if present
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            content = content[end + 3:].strip()
    return content.strip()


def fill_prompt(template: str, **kwargs) -> str:
    """Fill template placeholders using str.replace (avoids JSON {} conflict).

    Shared utility — previously duplicated verbatim in budget_check.py,
    adapt_weather.py, and add_couple_touch.py.
    """
    result = template
    for key, val in kwargs.items():
        result = result.replace("{" + key + "}", str(val))
    return result


# ── Markdown Prompt Templates (loaded from files) ────────────────

PARSE_INPUT_PROMPT = _load_md("parse_input_prompt.md")
PLAN_ITINERARY_PROMPT = _load_md("plan_itinerary_prompt.md")
COUPLE_COPY_PROMPT = _load_md("couple_copy_prompt.md")
WEATHER_ADAPT_PROMPT = _load_md("weather_adapt_prompt.md")
BUDGET_DOWNGRADE_PROMPT = _load_md("budget_downgrade_prompt.md")


# ── Inline Prompt Templates ─────────────────────────────────────
# Tidy: ITINERARY_PROMPT, COUPLE_MESSAGE_PROMPT, BUDGET_CHECK_PROMPT,
# and WEATHER_ADAPT were removed — they were M1 relics referenced only
# by tests, never by production code.

SYSTEM_PROMPT = """你是一个专业的中国情侣旅游规划师。你的任务是根据用户提供的目的地、
日期、预算和偏好，生成一份浪漫且可执行的情侣行程。

核心原则：
1. **浪漫节奏**：不赶场，每天上午/下午/晚间各最多2个活动，留出白时间。
2. **预算透明**：每一项活动标注预估花费，总花费不超过预算。
3. **天气自适应**：雨天自动推荐室内备选，高温避开正午户外活动。
4. **情侣共情**：每个活动附带一句温暖真挚的情侣寄语。
5. **本地真实**：推荐的景点、餐厅必须是目的地真实存在的。

输出格式为 JSON，结构如下：
{{
  "days": [
    {{
      "day_index": 0,
      "activities": [
        {{
          "period": "上午|下午|晚间",
          "name": "活动名称",
          "type": "景点|美食|室内|户外|文化|冒险|留白",
          "start_time": "HH:MM",
          "duration_min": 60,
          "description": "简短描述",
          "estimated_cost": 0,
          "location": "地点"
        }}
      ]
    }}
  ]
}}
"""


# ── Public API ───────────────────────────────────────────────────

__all__ = [
    # Shared utility
    "fill_prompt",
    # Markdown templates (M2+)
    "PARSE_INPUT_PROMPT",
    "PLAN_ITINERARY_PROMPT",
    "COUPLE_COPY_PROMPT",
    "WEATHER_ADAPT_PROMPT",
    "BUDGET_DOWNGRADE_PROMPT",
    # Inline templates
    "SYSTEM_PROMPT",
]
