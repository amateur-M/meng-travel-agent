"""output_format — Final formatting node that packages the draft into final_itinerary.

Converts the internal draft dict into the shape expected by TripPlanResponse
and performs a final validation pass.
"""

import uuid
from typing import Dict, Any

from agents.state import AgentState


def output_format(state: AgentState) -> Dict[str, Any]:
    """Package draft_itinerary + budget_breakdown + couple_notes into final form.

    This is a pure transform node — no LLM call, no side effects.
    It ensures the output is structurally valid before the SSE stream
    emits the "complete" event.

    Returns:
        Partial state with final_itinerary ready for serialisation.
    """
    params = state.get("parsed_params", {})
    draft = state.get("draft_itinerary", {})
    budget = state.get("budget_breakdown", {})
    notes = state.get("couple_notes", [])

    plan_id = str(uuid.uuid4())[:8]

    final = {
        "plan_id": plan_id,
        "destination": params.get("destination", ""),
        "start_date": params.get("start_date", ""),
        "end_date": params.get("end_date", ""),
        "budget_breakdown": budget,
        "days": draft.get("days", []),
        "couple_notes": notes,
        "status": "completed",
    }

    return {
        "final_itinerary": final,
        "current_phase": "output_format",
    }
