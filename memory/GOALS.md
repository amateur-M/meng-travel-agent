## Current Iteration Goals

**Current Milestone**: M6 — Real-time SSE Streaming (Next)

**Objective**: Stream itinerary generation progress to the frontend via SSE so users see planning unfold step-by-step.

### M5 Completion Summary (2026-10-02)

M5 is complete. Delivered:
- `rhythm_control` node: caps each period to ≤2 activities, injects period-aware 留白 slots
- `add_couple_touch` enhanced: 留白 templates split by period (晨光/午后/夜色), batch LLM prompt includes period guidance
- `CoupleMessage` frontend component: period-differentiated accent bars, inline in `TimelineCard`
- 留白 cards use dashed border + hidden cost for visual distinction
- Backend: 167 passed + 1 skipped; frontend tsc typecheck passed

### Tasks for Next Iteration (M6)

1. Strengthen SSE event types: `partial` (per-day itinerary chunks), `budget_alert`, `weather_swap`, `message` (couple note)
2. Build `useStream` hook for structured SSE consumption with auto-retry
3. Build `StreamingItinerary` component for progressive card rendering
4. Ensure stream output matches final result

### Acceptance Criteria (M6)

- User sees "正在查询天气..." → "正在搜索景点..." → "正在生成行程..." → "正在添加寄语..." progressively
- Each stage's output appears incrementally, not all at once
- SSE disconnect triggers auto-retry
- Streamed output equals final result

### Blockers

None
