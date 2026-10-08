"""LangGraph state graph — builds and compiles the travel-planning pipeline.

Graph topology (M4, post-P6 cleanup):

  parse_input
      │
      ├──→ fetch_weather ──┐
      ├──→ search_poi    ──┤
      └──→ search_food   ──┘
              │
        plan_itinerary
              │
        budget_check   ← deterministic in-place downgrade (no retry loop)
              │
        adapt_weather
              │
        add_couple_touch
              │
        output_format
              │
             END

P6: the conditional retry edge (budget_check → plan_itinerary) was removed.
M4 made budget_check apply a deterministic in-place downgrade and always set
downgrade_applied=True, making the retry branch permanently unreachable.
"""

from langgraph.graph import StateGraph, END

from agents.state import AgentState

from agents.nodes.parse_input import parse_input
from agents.nodes.fetch_weather import fetch_weather
from agents.nodes.search_poi import search_poi
from agents.nodes.search_food import search_food
from agents.nodes.plan_itinerary import plan_itinerary
from agents.nodes.rhythm_control import rhythm_control
from agents.nodes.budget_check import budget_check
from agents.nodes.adapt_weather import adapt_weather
from agents.nodes.add_couple_touch import add_couple_touch
from agents.nodes.output_format import output_format


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
    workflow.add_node("rhythm_control", rhythm_control)
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

    # ── core sequence: plan → rhythm → budget → weather → touch → output ──
    # M5: rhythm_control normalises periods (≤2 activities each, inject rest)
    # right after the draft is generated, before budget runs.
    # P6: direct edge replaces the former conditional retry loop.
    # budget_check now applies a deterministic in-place downgrade and
    # always routes forward — the plan_itinerary retry branch was dead code.
    workflow.add_edge("plan_itinerary", "rhythm_control")
    workflow.add_edge("rhythm_control", "budget_check")
    workflow.add_edge("budget_check", "adapt_weather")

    # ── polish & finalise ────────────────────────────────────────
    workflow.add_edge("adapt_weather", "add_couple_touch")
    workflow.add_edge("add_couple_touch", "output_format")
    workflow.add_edge("output_format", END)

    return workflow.compile()


# ── Module-level singleton ───────────────────────────────────────

graph = build_graph()
