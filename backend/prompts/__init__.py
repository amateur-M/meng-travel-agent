"""Prompt templates for the travel planning agent.

Templates are loaded from .md files for readability and version control.
The module also retains inline Python string templates for backward
compatibility with existing nodes.
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


# ── Markdown Prompt Templates (loaded from files) ────────────────

PARSE_INPUT_PROMPT = _load_md("parse_input_prompt.md")
PLAN_ITINERARY_PROMPT = _load_md("plan_itinerary_prompt.md")
COUPLE_COPY_PROMPT = _load_md("couple_copy_prompt.md")
WEATHER_ADAPT_PROMPT = _load_md("weather_adapt_prompt.md")
BUDGET_DOWNGRADE_PROMPT = _load_md("budget_downgrade_prompt.md")


# ── Inline Prompt Templates (M1 compatibility) ───────────────────

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

ITINERARY_PROMPT = """请为以下情侣旅行生成一份 {num_days} 天的详细行程：

**目的地**：{destination}
**日期**：{start_date} 至 {end_date}
**总预算**：{budget} 元
**偏好**：{preferences}
**节奏**：{pace}

**天气信息**：
{weather_summary}

**推荐景点**：
{poi_summary}

**推荐餐厅**：
{food_summary}

请生成每天上午、下午、晚间各时段的活动安排。每个活动需包含：名称、类型、预估花费、简短描述。
确保每日总花费不超过 {daily_budget} 元。
{extra_instructions}
"""

COUPLE_MESSAGE_PROMPT = """你是一个温柔细腻的文案写手，专为情侣旅行撰写寄语。

请为以下活动生成一句简短的情侣寄语（20字以内）：

**目的地**：{destination}
**活动**：{activity_name}
**活动类型**：{activity_type}

要求：
- 风格温暖真挚，不油腻不矫情
- 与目的地氛围和活动类型匹配
- 可以用"和你一起……"的句式，但不要千篇一律
"""

BUDGET_CHECK_PROMPT = """请检查以下行程的预算是否合理：

**总预算**：{budget} 元
**当前累计花费**：{current_spent} 元
**超预算**：{over_budget}

**当前行程摘要**：
{itinerary_summary}

如果超预算，请提供降级方案：
1. 将高价餐厅替换为人均100元以内的本地特色餐厅
2. 将收费景点替换为免费或低价的同类景点
3. 保持活动数量不变，只替换个别高价项目

输出 JSON：
{{
  "adjusted": true/false,
  "adjustments": ["调整说明1", "调整说明2"],
  "new_daily_costs": [100, 200, 150]
}}
"""

WEATHER_ADAPT = """请根据天气情况调整行程：

**天气数据**：
{weather_data}

**当前行程**：
{itinerary_summary}

调整规则：
- 雨天（中雨及以上）：将户外景点替换为室内备选（博物馆、咖啡馆、手工坊等）
- 高温（>35°C）：将正午（11:00-15:00）户外活动移至上午或傍晚
- 标注每次调整的原因

输出 JSON：
{{
  "swaps": [
    {{
      "day": 0,
      "period": "下午",
      "original": "洱海骑行",
      "replacement": "古城咖啡馆",
      "reason": "中雨，切换室内方案"
    }}
  ]
}}
"""


# ── Public API ───────────────────────────────────────────────────

__all__ = [
    # Markdown templates (new, M2+)
    "PARSE_INPUT_PROMPT",
    "PLAN_ITINERARY_PROMPT",
    "COUPLE_COPY_PROMPT",
    "WEATHER_ADAPT_PROMPT",
    "BUDGET_DOWNGRADE_PROMPT",
    # Inline templates (M1 backward compat)
    "SYSTEM_PROMPT",
    "ITINERARY_PROMPT",
    "COUPLE_MESSAGE_PROMPT",
    "BUDGET_CHECK_PROMPT",
    "WEATHER_ADAPT",
]
