"""LangGraph state graph — builds and compiles the travel-planning pipeline.

Graph topology (M1):

  parse_input
      │
      ├──→ fetch_weather ──┐
      ├──→ search_poi    ──┤
      └──→ search_food   ──┘
              │
        plan_itinerary ←──────────────┐
              │                       │
        budget_check ──(over)─────────┘  ←  loop, max 2 retries
              │ (ok)
        adapt_weather
              │
        add_couple_touch
              │
        output_format
              │
             END

Conditional edges:
  - budget_check → plan_itinerary  when over_budget AND retry_count < 2
  - budget_check → adapt_weather  otherwise
"""

from langgraph.graph import StateGraph, END

from agents.state import AgentState

from agents.nodes.parse_input import parse_input
from agents.nodes.fetch_weather import fetch_weather
from agents.nodes.search_poi import search_poi
from agents.nodes.search_food import search_food
from agents.nodes.plan_itinerary import plan_itinerary
from agents.nodes.budget_check import budget_check
from agents.nodes.adapt_weather import adapt_weather
from agents.nodes.add_couple_touch import add_couple_touch
from agents.nodes.output_format import output_format


# ── Router ───────────────────────────────────────────────────────

def _route_after_budget(state: AgentState) -> str:
    """Decide whether to retry planning or move on to weather adaptation.

    Retry condition: budget exceeded AND fewer than 2 retry attempts.
    Otherwise pass through to adapt_weather.
    """
    bb = state.get("budget_breakdown", {})
    over = bb.get("over_budget", False)
    downgrade_applied = bb.get("downgrade_applied", False)
    retries = state.get("retry_count", 0)

    if downgrade_applied:
        return "adapt_weather"
    if over and retries < 2:
        return "plan_itinerary"
    return "adapt_weather"


# ── Build ────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Assemble and compile the travel-planning StateGraph."""
    workflow = StateGraph(AgentState)

    # ── register nodes ───────────────────────────────────────────
    workflow.add_node("parse_input", parse_input)
    workflow.add_node("fetch_weather", fetch_weather)
    workflow.add_node("search_poi", search_poi)
    workflow.add_node("search_food", search_food)
    workflow.add_node("plan_itinerary", plan_itinerary)
    workflow.add_node("budget_check", budget_check)
    workflow.add_node("adapt_weather", adapt_weather)
    workflow.add_node("add_couple_touch", add_couple_touch)
    workflow.add_node("output_format", output_format)

    # ── entry point ──────────────────────────────────────────────
    workflow.set_entry_point("parse_input")

    # ── fan-out: parse_input → 3 parallel fetchers ──────────────
    workflow.add_edge("parse_input", "fetch_weather")
    workflow.add_edge("parse_input", "search_poi")
    workflow.add_edge("parse_input", "search_food")

    # ── fan-in: all three fetchers → plan_itinerary ─────────────
    workflow.add_edge("fetch_weather", "plan_itinerary")
    workflow.add_edge("search_poi", "plan_itinerary")
    workflow.add_edge("search_food", "plan_itinerary")

    # ── core loop: plan → budget → (retry?) → weather ───────────
    workflow.add_edge("plan_itinerary", "budget_check")

    workflow.add_conditional_edges(
        "budget_check",
        _route_after_budget,
        {
            "plan_itinerary": "plan_itinerary",
            "adapt_weather": "adapt_weather",
        },
    )

    # ── polish & finalise ────────────────────────────────────────
    workflow.add_edge("adapt_weather", "add_couple_touch")
    workflow.add_edge("add_couple_touch", "output_format")
    workflow.add_edge("output_format", END)

    return workflow.compile()


# ── Module-level singleton ───────────────────────────────────────

graph = build_graph()
