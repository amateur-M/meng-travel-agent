## Current Iteration Goals

**Current Milestone**: M4 — Budget Transparency & Weather Adaptation

**Objective**: Make budget usage transparent in the frontend and strengthen weather-based itinerary adaptation in the backend.

### Tasks for This Iteration

1. Add backend budget alert and downgrade recommendations when total spent approaches or exceeds budget.
2. Add backend weather switching logic for rain and high-temperature days.
3. Build frontend `BudgetAlerts` for over-budget warnings and downgrade suggestions.
4. Build frontend `WeatherBadge` to surface weather swaps and reasons.

### Acceptance Criteria

- Activities show estimated costs, and the itinerary header shows total budget and spending progress.
- Spending over 90% triggers a yellow warning; over 100% triggers a downgrade plan.
- Rainy days swap outdoor activities for indoor alternatives and mark the reason in the UI.
- High-temperature days move outdoor activities to morning or evening.

### Blockers

None
