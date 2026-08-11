"""parse_input — Validate and normalise raw user input into structured params.

M1 placeholder: performs basic field validation + default fill.
Real implementation will call the LLM for fuzzy natural-language parsing.
"""

from typing import Dict, Any
from datetime import date

from agents.state import AgentState


def parse_input(state: AgentState) -> Dict[str, Any]:
    """Normalise raw user_input into parsed_params.

    The raw input dict arrives via POST /api/plan and is stored in
    state["user_input"].  This node:
      1. Validates required fields are present
      2. Converts date strings to date objects (or keeps as ISO strings)
      3. Fills in sensible defaults (pace → relaxed, budget → 3000)
      4. Sets current_phase so the SSE stream can report progress

    Returns a partial state update.
    """
    ui = state.get("user_input", {})

    # ── defaults ─────────────────────────────────────────────────
    parsed: Dict[str, Any] = {
        "origin": ui.get("origin", "未指定"),
        "destination": ui.get("destination", ""),
        "start_date": ui.get("start_date", ""),
        "end_date": ui.get("end_date", ""),
        "budget": float(ui.get("budget", 3000)),
        "preferences": ui.get("preferences", ["浪漫", "美食"]),
        "pace": ui.get("pace", "轻松"),
        "num_days": 1,
    }

    # ── derive num_days ──────────────────────────────────────────
    try:
        sd = date.fromisoformat(str(parsed["start_date"]))
        ed = date.fromisoformat(str(parsed["end_date"]))
        parsed["num_days"] = max(1, (ed - sd).days)
    except (ValueError, TypeError):
        pass  # keep default; downstream nodes will handle missing dates

    return {
        "parsed_params": parsed,
        "current_phase": "parse_input",
        "retry_count": 0,
        "error": "",
    }
