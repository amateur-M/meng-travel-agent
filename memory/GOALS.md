## Current Iteration Goals

**Current Milestone**: M1 — Backend Core Agent Engine

**Objective**: Implement the full LangGraph travel planning pipeline that produces structured itinerary JSON from input parameters.

### Tasks for This Iteration

1. Implement all 8 Nodes:
   - gather_input — parse and validate user input
   - fetch_weather — query weather (mock data for M1)
   - search_pois — search attractions/restaurants (mock data for M1)
   - generate_itinerary — LLM-powered initial itinerary generation
   - apply_budget — budget calculation and downgrade logic
   - weather_adapt — weather-condition based adjustments
   - add_couple_messages — generate couple messages per activity
   - finalize_plan — final validation and output

2. Write LLM prompt templates

3. Define Pydantic data models (TripPlan, DayPlan, Activity, BudgetSummary)

4. Write test_agent.py unit tests

### Acceptance Criteria

- Input: { destination: "Dali", start_date: "2026-09-01", end_date: "2026-09-03", budget: 5000, preferences: ["romantic", "food"] }
- Output: structured TripPlan JSON with morning/afternoon/evening activities, estimated costs, and couple messages per day
- All unit tests pass

### Blockers

None

