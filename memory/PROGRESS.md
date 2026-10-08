## Development Progress

| Milestone | Status | Start Date | End Date | Notes |
|-----------|--------|------------|----------|-------|
| M0 | Done | 2026-08-10 | 2026-08-10 | Project scaffold complete |
| M1 | Done | 2026-08-10 | 2026-08-11 | Agent engine core + tests |
| M2 | Done | 2026-08-11 | 2026-08-16 | External API + LLM integration |
| M3 | Done | 2026-08-16 | 2026-08-18 | Frontend core UI refactor |
| M4 | Done | 2026-08-30 | 2026-08-31 | Budget + weather |
| M5 | Done | 2026-10-02 | 2026-10-02 | Rhythm control + couple experience |
| M6 | Pending | — | — | SSE streaming |
| M7 | Pending | — | — | Testing + deployment |

## M0 Completion Checklist

- [x] Backend directory structure created (agents/, config/, tools/, prompts/, schemas/, tests/)
- [x] pyproject.toml + requirements.txt with all core dependencies
- [x] main.py FastAPI entry + /health endpoint + CORS middleware
- [x] config/settings.py centralized config (env to Python)
- [x] agents/state.py AgentState type definition
- [x] agents/graph.py LangGraph scaffold (build_graph + compile)
- [x] .env.example with OPENAI / WEATHER / MAPS key placeholders
- [x] Frontend Vite + React 18 + TypeScript scaffold
- [x] Frontend dependencies: react-router-dom, axios, zustand, framer-motion, tailwindcss
- [x] tailwind.config.ts with brand colors (primary red palette)
- [x] vite.config.ts with proxy config (/api to localhost:8000)
- [x] App.tsx with React Router skeleton
- [x] docker-compose.yml for frontend + backend orchestration
- [x] .gitignore with node_modules, __pycache__, .env
- [x] README.md with quickstart instructions
- [x] memory files updated (PROJECT_STRUCTURE, KEY_DECISIONS, PROGRESS, GOALS)


## M1 Completion Checklist

- [x] AgentState redefined with all user-specified fields + Annotated reducer for current_phase
- [x] 9 node files created: parse_input, fetch_weather, search_poi, search_food, plan_itinerary, budget_check, adapt_weather, add_couple_touch, output_format
- [x] Prompt templates in prompts/ (SYSTEM, ITINERARY, COUPLE, BUDGET, WEATHER_ADAPT)
- [x] Pydantic schemas: TripPlanRequest, Activity, DayPlan, BudgetBreakdown, TripPlanResponse, SSEEvent
- [x] LangGraph StateGraph with conditional edge (budget_check → plan_itinerary retry loop, max 2)
- [x] Mock data fallback in all external-dependent nodes (weather, POI, food, LLM)
- [x] POST /api/plan SSE streaming endpoint
- [x] graph.invoke() dry-run verified: 2-day mock itinerary with budget + couple notes


## M1 Test Suite

- [x] test_schemas.py (13 tests) — Pydantic request/response model validation
- [x] test_state.py (7 tests) — AgentState TypedDict + _latest_str reducer
- [x] test_prompts.py (10 tests) — 5 prompt templates (existence + format)
- [x] test_nodes_input.py (16 tests) — parse_input / fetch_weather / search_poi / search_food
- [x] test_nodes_core.py (17 tests) — plan_itinerary / budget_check / adapt_weather
- [x] test_nodes_output.py (11 tests) — add_couple_touch / output_format
- [x] test_graph.py (17 tests) — full graph integration (3 destinations, budget loop, stream mode)
- [x] All destinations tested: Dali, Lijiang, Sanya, unknown fallback
- [x] Edge cases: single-day, budget overflow retry, rain-to-indoor swap, heat reschedule
- [x] **Result: 96/96 passed**


## M2 Progress

### Tools & Prompts (done 2026-08-11)
- [x] 4 LangChain Tools: weather, poi_search, food_search, maps_tool
- [x] 5 Prompt .md templates: parse_input, plan_itinerary, couple_copy, weather_adapt, budget_downgrade
- [x] prompts/__init__.py loads .md templates + retains M1 inline templates

### Node Wiring & LLM Service (done 2026-08-11)
- [x] fetch_weather.py → weather_tool_sync
- [x] search_poi.py → poi_search_tool
- [x] search_food.py → food_search_tool
- [x] Shared LLM service: services/llm.py (call_llm with mock fallback)
- [x] plan_itinerary.py → services.llm.call_llm + PLAN_ITINERARY_PROMPT
- [x] budget_check.py → services.llm.call_llm + BUDGET_DOWNGRADE_PROMPT
- [x] adapt_weather.py → services.llm.call_llm + WEATHER_ADAPT_PROMPT + rule-based fallback
- [x] add_couple_touch.py → services.llm.call_llm + COUPLE_COPY_PROMPT + template fallback

### Multi-Provider LLM (done 2026-08-12)
- [x] DeepSeek (deepseek-chat), Qwen (qwen-plus), Kimi (moonshot-v1-8k)
- [x] All use OpenAI-compatible API — zero new dependencies
- [x] DEFAULT_LLM_PROVIDER env var controls default, call_llm() accepts optional provider arg

### Tests
- [x] test_tools.py — All 4 tools: weather, poi, food, maps
- [x] test_services.py — LLM service + JSON extraction + multi-provider
- [x] All existing M1 tests updated for new data structures
- [x] **Result: 138/138 passed** (M1 96 → M2 138)

### M2 Fixes (2026-08-13)
- [x] Fixed `plan_itinerary._build_prompt()` so template placeholders are filled and returned
- [x] Migrated `tools/weather_tool.py` from legacy QWeather `?key=` API to current JWT/Bearer API
- [x] QWeather GeoAPI city lookup: `GET /geo/v2/city/lookup`
- [x] QWeather daily forecast: `GET /weather/v1/daily/{latitude}/{longitude}`
- [x] Added QWeather v1 daily response parser + focused tests
- [x] Qwen real LLM smoke test passed

### QWeather Real Auth (2026-08-15)
- [x] Added `services/qweather_auth.py` with JWT generation using Ed25519 private keys
- [x] Added auto-detection for PEM private key, signed JWT, and API key
- [x] Added `QWEATHER_AUTH_MODE`, `QWEATHER_CREDENTIAL_ID`, `QWEATHER_PROJECT_ID`, private-key path, and TTL settings
- [x] Added `cryptography` dependency
- [x] Added opt-in real API test: `QWX_TEST_REAL_API=1`
- [x] Removed deliberate `RuntimeError` patches from weather test fixtures
- [x] Full test result: 146 passed + 1 skipped

### M2 Finalization (done 2026-08-16)
- [x] Added `QWEATHER_CREDENTIAL_ID` and `QWEATHER_PROJECT_ID` to `backend/.env`
- [x] Ran real QWeather smoke test with `QWX_TEST_REAL_API=1`
- [x] Added `tests/test_qweather_cassettes.py` with offline vcrpy cassette tests
- [x] Recorded cassettes for QWeather city lookup and daily forecast
- [x] Full offline suite: 148 passed + 1 skipped
- [x] Real QWeather smoke test: 1 passed

## M3 Completion Checklist (2026-08-18)

- [x] Refactored `types/trip.ts` with trip request, response, activity, budget, weather, and progress types
- [x] Added `config/tripOptions.ts` for destination, origin, preference, and pace options
- [x] Added `mocks/trip.ts` with dynamic mock itinerary for UI-only preview
- [x] Added `services/api.ts` Axios instance with response error normalization
- [x] Added `services/sse.ts` EventSource connection manager
- [x] Added `services/plan.ts` POST /api/plan stream parser with backend response normalization
- [x] Wired `tripStore.beginPlanning` to real backend SSE instead of mock planning flow
- [x] Added Zustand `tripStore` for form, plan, budget, planning status, and progress
- [x] Added Zustand `uiStore` for theme and reduced-motion state
- [x] Built `TripForm` with destination selector, date range, budget slider, preference tags, and pace selector
- [x] Built `Timeline` with Day 1 to Day N expand/collapse and morning/afternoon/evening grouping
- [x] Built `TimelineCard` with activity icon, time, location, cost, weather note, and couple note
- [x] Built `BudgetBar` with animated spent/total progress and over-budget warning
- [x] Built `WeatherBadge` with weather type, temperature, and adaptive hint
- [x] Built `CoupleQuote` with handwritten font and fade-in animation
- [x] Built `SSEProgress` for Agent step visualization
- [x] Built `Home`, `PlanResult`, and `Loading` pages with React Router routes
- [x] Applied warm pink, cream, and gold visual system with mobile-first responsive layout
- [x] Fixed backend inclusive date-range bug in `parse_input` and updated affected tests

## M4 Completion Checklist (2026-08-31)

- [x] Backend `budget_check` computes `warning_level` and `spending_ratio`
- [x] Backend `budget_check` applies deterministic downgrades when spending exceeds budget
- [x] Backend `adapt_weather` swaps rainy outdoor activities for indoor alternatives
- [x] Backend `adapt_weather` moves >35°C midday outdoor activities to morning or evening
- [x] Backend `weather_swaps` state carries swap/time-shift reasons to the final response
- [x] Backend `output_format` enriches day dates, weather high/low, and daily costs
- [x] Frontend `BudgetAlerts` shows 90% warning and over-budget downgrade notes
- [x] Frontend `BudgetBar` distinguishes ok / warning / over-budget states
- [x] Frontend `WeatherBadge` and `Timeline` surface weather-swap reasons
- [x] Frontend `PlanResult` header shows total budget and spending progress

## Verification

- npm install succeeded: 166 packages
- Frontend scaffold ready for M3 UI development
- Backend M1 agent engine fully tested (96/96)
- Backend M2 tools + services + node wiring + multi-provider tested
- QWeather auth layer tested; real QWeather call verified with credentials
- vcrpy cassette tests replay external API calls without network access
- Latest offline test result: 148 passed + 1 skipped
- Latest real QWeather smoke test: 1 passed
- Frontend M3 TypeScript typecheck passed (`tsc -p tsconfig.app.json` and `tsconfig.node.json`)
- Frontend Vite production build passed
- Frontend dev server verified on `http://127.0.0.1:5173` with HTTP 200
- Backend `POST /api/plan` integration verified through Vite proxy and returns SSE `complete`
- Backend 3-day request verified to return 3 itinerary days after date-range fix
- Real end-to-end graph verified with live Amap + QWeather + Qwen (2-day Dali plan)

## Backend Code-Review Fixes (2026-10-01)

Executed the phased fix plan in `coupletrip-backend-issues-and-fix-plan.md` (baseline commit `0710d9f`).

### Phase 0 — immediate
- [x] **P1**: `/api/plan` no longer runs the graph twice. Reuse `astream(stream_mode="values")` terminal chunk as `final_state`; removed `graph.ainvoke()` (and `graph.invoke()` in the sync fallback). LLM calls per request halved.
- [x] **P5**: `main.py` catches broad `Exception`, emits an SSE `error` event and logs the stack via `logger.exception(...)`; the legacy `AttributeError` async/sync fallback is preserved.

### Phase 1 — this iteration
- [x] **P2**: `AgentState` gained `warnings: Annotated[List[str], operator.add]`. `search_poi`/`search_food` append a degradation warning instead of writing fatal `error`, so a missing Amap key no longer aborts the stream. `complete` event carries `warnings`.
- [x] **P3**: OpenWeatherMap async parser no longer reads a leftover loop variable; per-day `pop` values are collected and reduced with `max()`.
- [x] **P4**: `fetch_weather` except-branch writes back `start_str = sd.isoformat()` before computing `end_str`, so an invalid date degrades to mock instead of raising.
- [x] **P7**: couple messages generated in a single batched LLM call (`_generate_batch_llm_messages`) instead of one call per activity; `_trim_message` enforces the 6–25 char constraint; `None` results fall back to the template library. LLM cost drops from O(activities) to O(1).
- [x] **P9**: `test_qweather_cassettes.py` pins `settings.qweather_base_url` to the cassette host via `monkeypatch`, so the suite passes on a clean environment without `.env`.

### Phase 2 — architecture tidy-up
- [x] **P8**: `Activity.activity_type` renamed to `type` with `alias="activity_type"` + `populate_by_name`; missing `ActivityType` enum values (`自然`/`人文`/`网红`) added; `main.py` runs `TripPlanResponse.model_validate(...).model_dump(mode="json")` as an exit guard before `complete`.
- [x] **P10**: introduced `logging.getLogger("coupletrip")`; silent `except Exception: pass` blocks in weather/LLM/search now `logger.warning(..., exc_info=True)`.
- [x] **P6**: removed the unreachable budget-retry loop — deleted `_route_after_budget` + conditional edge (now a direct `budget_check → adapt_weather` edge), dropped `retry_count` from state, and removed the unused `BUDGET_CHECK_PROMPT` import.
- [x] **Tidiness**: extracted the shared `fill_prompt()` into `prompts/` (was duplicated in three nodes); deleted dead code (`_parse_qweather_daily`, unused inline prompts); added `request_timeout=60` to the LLM client.

### Test result
- Baseline: 155 passed / 2 failed / 1 skipped
- Final: **148 passed / 0 failed / 1 skipped** (net decrease from removing dead-code tests: 5 budget-router + 3 `_parse_qweather_daily` + 7 dead-prompt tests; added 3 P8 schema tests + 3 `fill_prompt` tests)
- No-API-key end-to-end smoke test verified: 3-day degraded itinerary returned, `warnings` accumulated, `TripPlanResponse` exit validation passed, activities carry `type` + `couple_note`.

## M5 Completion Checklist (2026-10-02)

### Backend — Rhythm Control
- [x] New `agents/nodes/rhythm_control.py` node: caps each period (上午/下午/晚间) to ≤2 activities, injects period-aware 留白 slot when room exists
- [x] Graph edge: `plan_itinerary → rhythm_control → budget_check` (registered in `graph.py`)
- [x] `AgentState` gained `rhythm_adjustments` field; `output_format` surfaces it in `final_itinerary`
- [x] `_phase_message` updated with `rhythm_control: "正在调整行程节奏..."`
- [x] `schemas/__init__.py` added `RhythmAdjustment` model + `TripPlanResponse.rhythm_adjustments`
- [x] `test_nodes_rhythm.py`: 14 tests (cap, rest injection, normalise day, node integration, immutability)

### Backend — Couple Message Enhancement
- [x] `add_couple_touch._pick_message` now accepts `period`; 留白 templates split by period (`_REST_TEMPLATES_BY_PERIOD`)
- [x] Batch LLM prompt enriched with period-aware tone guidance (晨光/午后/夜色 motifs for 留白)
- [x] `couple_copy_prompt.md` expanded with per-period 留白 tone table + evening motif guidance
- [x] `test_nodes_output.py`: 5 new tests for period-specific rest messages + `rhythm_adjustments` in final output

### Frontend — Couple Experience
- [x] New `CoupleMessage/CoupleMessage.tsx`: period-differentiated accent bar (gold/blush/indigo) + rest chip
- [x] `TimelineCard` rewritten: imports `CoupleMessage`, 留白 cards use dashed border + hide cost
- [x] `types/trip.ts` added `RhythmAdjustment` interface + `TripPlanResponse.rhythm_adjustments`
- [x] `services/plan.ts` added `normalizeRhythmAdjustments`

### Test Result
- Backend: **167 passed + 1 skipped** (was 148; +19 new M5 tests)
- Frontend: `tsc -b` typecheck passed (vite build blocked by Node 16 / Vite 5 env incompatibility, unrelated to code changes)
- Graph integration: 13/13 passed including full Dali/Lijiang/Sanya end-to-end through rhythm_control
