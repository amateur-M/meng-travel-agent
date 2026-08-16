## Development Progress

| Milestone | Status | Start Date | End Date | Notes |
|-----------|--------|------------|----------|-------|
| M0 | Done | 2026-08-10 | 2026-08-10 | Project scaffold complete |
| M1 | Done | 2026-08-10 | 2026-08-11 | Agent engine core + tests |
| M2 | Done | 2026-08-11 | 2026-08-16 | External API + LLM integration |
| M3 | Done | 2026-08-16 | 2026-08-16 | Frontend basic UI |
| M4 | Pending | — | — | Budget + weather |
| M5 | Pending | — | — | Rhythm + couple messages |
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

## M3 Completion Checklist (2026-08-16)

- [x] Added `frontend/src/types/trip.ts` matching backend schemas
- [x] Added `frontend/src/services/plan.ts` with `POST /api/plan` SSE parsing
- [x] Built `TripForm` with origin, destination, dates, budget, preferences, and pace
- [x] Built `ItineraryCard` with date, weather, period grouping, and daily cost
- [x] Built `ActivityItem` with type badge, time, location, cost, and couple note
- [x] Built `BudgetBar` with total spent / total budget progress
- [x] Wired `Home` page and replaced the scaffold route
- [x] Added `lucide-react` icon dependency
- [x] Verified frontend build and frontend proxy to `POST /api/plan`

## Verification

- npm install succeeded: 166 packages
- Frontend scaffold ready for M3 UI development
- Backend M1 agent engine fully tested (96/96)
- Backend M2 tools + services + node wiring + multi-provider tested
- QWeather auth layer tested; real QWeather call verified with credentials
- vcrpy cassette tests replay external API calls without network access
- Latest offline test result: 148 passed + 1 skipped
- Latest real QWeather smoke test: 1 passed
- Frontend M3 build passed with Vite + TypeScript
- Frontend proxy integration passed: `POST /api/plan` returns SSE `complete`
