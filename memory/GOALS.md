## Current Iteration Goals

**Current Milestone**: M3 — Frontend Basic UI

**Objective**: Implement the trip input form and itinerary card display, then connect them to the existing `POST /api/plan` SSE endpoint.

### Tasks for This Iteration

1. Define TypeScript types matching the backend `TripPlanRequest` and `TripPlanResponse`.
2. Build `TripForm` with origin, destination, dates, budget, preferences, and pace inputs.
3. Build `ItineraryCard`, `ActivityItem`, and `BudgetBar` components.
4. Add a frontend API layer that calls `POST /api/plan` and consumes the SSE `complete` event.
5. Apply responsive Tailwind layout for mobile single-column and desktop two-column.

### Acceptance Criteria

- Submitting `TripForm` successfully calls `POST /api/plan`.
- The returned itinerary is displayed as time-axis cards with date, weather, activities, estimated cost, and couple note.
- `BudgetBar` reflects total spent versus total budget.
- Mobile layout uses one column and desktop uses two columns.

### Blockers

None
