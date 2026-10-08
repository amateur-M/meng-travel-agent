## Key Design Decisions

### 1. Frontend Build Tool: Vite (not CRA / Next.js)

**Decision**: Use Vite 5+

**Rationale**:
- Vite is the community default for new React projects; Create React App is deprecated
- Cold-start dev server in under 1 second, instant HMR
- Native TypeScript + ESM support, no extra config
- Built-in dev proxy (`vite.config.ts` proxy to backend), no CORS hassles
- Next.js SSR is unnecessary for this SPA project

### 2. State Management: Zustand (not Redux / Context)

**Decision**: Use Zustand 4+

**Rationale**:
- Minimal API (a single `create` function), near-zero learning curve
- No Provider wrapping required, cleaner component tree
- Selector-based subscriptions prevent unnecessary re-renders
- First-class TypeScript inference
- Redux boilerplate is overkill for this project size; Context performs poorly with frequent updates

### 3. Backend Directory Structure: Flat (no `app/` sub-package)

**Decision**: Place `main.py` directly under `backend/`, with flat modules (`agents/`, `config/`, `schemas/`, `tools/`)

**Rationale**:
- Few modules at project start, an `app/` wrapper adds path depth with no benefit
- `python main.py` from `backend/` root reduces cognitive overhead
- Can introduce an `app/` wrapper later if module count exceeds 20+

### 4. Python Package Management: pyproject.toml + requirements.txt

**Decision**: Maintain both `pyproject.toml` (Poetry standard) and `requirements.txt` (pip compatible)

**Rationale**:
- `pyproject.toml` is the modern Python ecosystem standard with better lockfile management via Poetry
- `requirements.txt` provides a one-command pip install fallback, lowering the entry barrier
- Both can be derived from each other with minimal maintenance cost

### 5. HTTP Client: axios (not fetch)

**Decision**: Use axios for frontend API calls

**Rationale**:
- Automatic JSON parsing, no manual `.json()` calls
- Request/response interceptors for unified loading, error, and auth handling
- Simple timeout configuration
- `fetch` error status handling is unintuitive (does not throw on 4xx/5xx)

### 6. UI Animation: Framer Motion

**Decision**: Use Framer Motion 11+

**Rationale**:
- De facto standard in React ecosystem, declarative and intuitive API
- LayoutGroup and AnimatePresence support card enter/exit animations natively
- Non-invasive with Tailwind CSS, layers cleanly on top

### 7. Real-time Updates: SSE (not WebSocket)

**Decision**: Push itinerary generation progress via Server-Sent Events

**Rationale** (restated from ARCHITECTURE):
- Progress notifications are unidirectional (server to client), SSE covers this fully
- Browser-native `EventSource` API, zero extra dependencies
- Automatic reconnection, lighter protocol
- WebSocket reserved for potential future multi-user collaboration scenarios



### 8. Graph Topology: Conditional Edge for Budget Retry (SUPERSEDED — see #19)

> **Superseded 2026-10-01 (P6).** The conditional retry edge was unreachable dead code once M4 moved budget handling to an in-place deterministic downgrade. `_route_after_budget`, the conditional edge, and `retry_count` were removed; `budget_check → adapt_weather` is now a plain direct edge. See decision #19.

**Decision (historical)**: budget_check → plan_itinerary used a conditional edge (not a fixed loop).

**Rationale (historical)**:
- Budget may be exceeded multiple times after adjustment; a conditional edge with a router function (`_route_after_budget`) checks `over_budget` AND `retry_count < 2` before looping back
- Capping at 2 retries prevents infinite loops from irreconcilable budgets
- When budget is acceptable (or retries exhausted), the edge routes to `adapt_weather`

### 9. Node Fan-out: parse_input → 3 parallel fetchers

**Decision**: `parse_input` fans out to `fetch_weather`, `search_poi`, and `search_food` via three parallel edges.

**Rationale**:
- All three fetchers depend only on `parsed_params` (already set by `parse_input`), not on each other
- Running them as parallel edges signals the intent for future async execution, even though LangGraph executes them sequentially in M1
- The `current_phase` field uses an `Annotated[str, _latest_str]` reducer so concurrent writes from all three don't collide

### 10. Mock-first Strategy in M1

**Decision**: All external-dependent nodes (fetch_weather, search_poi, search_food, plan_itinerary) include a mock/fallback path so the graph runs without API keys.

**Rationale**:
- Enables immediate testing of the full graph topology without configuring external services
- Each node checks for API key availability and falls back gracefully
- M2 will replace mocks with real API calls without changing the graph structure

### 11. QWeather Authentication: Auto-detect PEM / JWT / API Key

**Decision**: `services/qweather_auth.py` generates QWeather-compatible Ed25519 JWTs when `WEATHER_API_KEY` contains a PEM private key, passes through already-signed JWTs, and sends short values as `X-QW-Api-Key`.

**Rationale**:
- QWeather's current API authenticates via JWT signed with Ed25519, or via an API key header
- The existing `.env` contained a private key rather than a signed JWT, so the old Bearer request was guaranteed to fail
- Keeping auto-detection avoids breaking either JWT or API Key deployments
- `QWEATHER_CREDENTIAL_ID` and `QWEATHER_PROJECT_ID` are required only when generating a JWT

### 12. QWeather Current API Shape

**Decision**: Use QWeather's current endpoint layout instead of the legacy `?key=` endpoints.

**Rationale**:
- City lookup: `GET {QWEATHER_BASE_URL}/geo/v2/city/lookup?location=...`
- Daily forecast: `GET {QWEATHER_BASE_URL}/weather/v1/daily/{latitude}/{longitude}`
- Legacy `geoapi.qweather.com` and `devapi.qweather.com/v7` endpoints return 404/403 for current credentials

### 13. Real External API Tests Are Opt-in

**Decision**: Unit tests do not patch weather fetchers with forced `RuntimeError`; external weather credentials are disabled by default, and real QWeather calls run only when `QWX_TEST_REAL_API=1`.

**Rationale**:
- Keeps the default test suite fast and deterministic
- Allows the same tests to exercise real QWeather when the operator explicitly opts in
- The opt-in smoke test calls `_fetch_qweather_sync` directly, bypassing mock fallback

### 14. Travel Date Range Is Inclusive

**Decision**: `parse_input` computes `num_days` as `(end_date - start_date).days + 1`.

**Rationale**:
- Users naturally expect a trip from 2026-09-01 to 2026-09-03 to contain three travel days
- Downstream nodes already consume `num_days` as an inclusive day count when generating weather and itinerary
- The prior exclusive calculation silently dropped the return date from multi-day plans

### 15. Budget Downgrade Is Applied Deterministically

**Decision**: `budget_check` always produces and applies a deterministic downgrade when the draft exceeds the budget, even when no LLM key is configured.

**Rationale**:
- The M1 budget-retry loop regenerated the itinerary but could silently leave the final plan over budget
- A deterministic POI/restaurant replacement guarantees that the returned plan matches the transparent budget state
- Once a downgrade is applied the flow proceeds straight to `adapt_weather` so regenerating the draft does not undo the savings (the former `_route_after_budget` router was removed in P6 — see decision #19)
- The LLM remains useful for richer reasoning, but it is treated as an optional enhancement rather than a correctness dependency

### 16. Weather Adjustments Are Returned As Structured Events

**Decision**: `adapt_weather` stores each rain swap and high-temperature time shift in `weather_swaps`, and the final API response exposes them as `WeatherSwap` objects.

**Rationale**:
- Acceptance requires the UI to mark *why* an activity changed, not just show a final weather note
- A structured list is easier for the frontend to group by `day_index` and render alongside `WeatherBadge`
- Keeping `adjustment_type` (`swap` / `time_shift`) leaves room for future weather rules without changing the response shape

### 17. Budget Warnings Are Modeled As Three Levels

**Decision**: `BudgetBreakdown` uses `warning_level` (`ok` / `warning` / `over`) and `spending_ratio`.

**Rationale**:
- The frontend can distinguish `<90%`, `90%–100%`, and `>100%` without duplicating threshold logic
- `spending_ratio` keeps the API useful for future budget charts and progress indicators
- The existing boolean `over_budget` is retained for backward compatibility and fast conditional checks

### 18. POI, Restaurant, and Route Data Come From Amap

**Decision**: Replace the local `_MOCK_POI`, `_MOCK_FOOD`, and haversine route estimates with live Amap Web Service calls through `services/amap.py`.

**Rationale**:
- The previous databases only covered five destinations and went stale by definition
- Amap supplies real attractions, museums, restaurants, ratings, per-person costs, and driving routes for every supported destination
- A stable GB/T 2260 `CITY_ADCODE` map keeps the `place/text` `city` parameter reliable without depending on the geocoding service, which is not enabled for the current key
- Normalisation in the tools preserves the schema consumed by downstream nodes, so the graph contract does not change
- Search failures now surface through `AgentState.error` instead of silently substituting fake results

### 19. Budget Handling Is a Direct Edge (Retry Loop Removed)

**Decision** (2026-10-01, P6): `budget_check → adapt_weather` is a plain direct edge. `_route_after_budget`, the conditional edge, and the `retry_count` state field were removed.

**Rationale**:
- Since M4, `budget_check` applies a deterministic in-place downgrade whenever the draft exceeds budget, so the router always resolved to `adapt_weather` and the `plan_itinerary` branch was unreachable dead code
- Removing it makes the graph topology match actual runtime behaviour and eliminates the misleading `retry_count` mechanism
- Supersedes decision #8

### 20. Soft Failures Accumulate As `warnings`, Not `error`

**Decision** (2026-10-01, P2): `AgentState` carries `warnings: Annotated[List[str], operator.add]`. Recoverable search failures (`search_poi`/`search_food`) append a warning; only truly fatal conditions set `error`. The `complete` SSE event attaches `warnings`.

**Rationale**:
- The graph can still produce a full itinerary from an empty candidate list, so a missing Amap key or a network blip must not abort the stream
- `operator.add` lets the three parallel fetchers each append without reducer collisions
- Surfacing `warnings` to the frontend lets it flag "partially degraded data" instead of showing a hard error

### 21. Response Schema Is Enforced At The Exit

**Decision** (2026-10-01, P8): before emitting `complete`, `main.py` runs `TripPlanResponse.model_validate(final).model_dump(mode="json")`. `Activity` exposes `type` with `alias="activity_type"` and `populate_by_name=True`.

**Rationale**:
- Previously the Pydantic response model was decorative — node output was `json.dumps`'d directly, so field drift silently reached the frontend
- The alias aligns the schema with the `type` key the nodes actually emit and the frontend consumes, while `populate_by_name` keeps `Activity(type=...)` construction working
- Exit validation turns any future field drift into a caught error rather than a silent contract break

### 22. Couple Messages Are Generated In One Batched LLM Call

**Decision** (2026-10-01, P7): `add_couple_touch` generates all activity messages in a single LLM call returning a JSON array, instead of one call per activity.

**Rationale**:
- The per-activity loop meant 3 days × ~6 activities = ~18 serial calls (doubled by the old P1 double-run), risking multi-minute requests
- Batching drops LLM cost from O(activities) to O(1); failed/missing entries fall back to the template library via `_pick_message`, and `_trim_message` enforces the 6–25 char constraint

### 23. Degradation Is Observable Via Structured Logging

**Decision** (2026-10-01, P10): a project-wide `logging.getLogger("coupletrip")` logger replaces silent `except Exception: pass` blocks in weather/LLM/search paths with `logger.warning(..., exc_info=True)`.

**Rationale**:
- The whole chain has mock fallbacks, but with zero logging there was no way in production to distinguish real data from a mock, making triage guesswork
- `exc_info=True` preserves the stack for debugging while keeping the request flowing through the degraded path

### 24. Rhythm Control Is a Separate Deterministic Node (M5)

**Decision** (2026-10-02): A new `rhythm_control` node sits between `plan_itinerary` and `budget_check`. It deterministically caps each period to ≤2 activities and injects period-aware 留白 slots when room exists.

**Rationale**:
- `plan_itinerary` already hints at the rhythm via prompt, but prompt-only constraints are soft — LLM output can still produce 3+ activities per period
- A separate node mirrors the established `budget_check` / `adapt_weather` pattern (deterministic transform, no LLM call), keeping the graph's correctness guarantees off the LLM
- Placing it before `budget_check` means cost capping works on the already-normalised plan, avoiding double-processing
- Rest injection is capped at `_MAX_PER_PERIOD` so it never violates the hard ≤2 constraint — a full period without rest is left as-is rather than overstuffing

### 25. 留白 Couple Messages Are Differentiated by Period (M5)

**Decision** (2026-10-02): `add_couple_touch._pick_message` selects period-specific 留白 templates (`_REST_TEMPLATES_BY_PERIOD`), and the batch LLM prompt asks for period-aware imagery (晨光/午后/夜色).

**Rationale**:
- The M2 `couple_copy_prompt.md` already guided tone by activity type but treated all 留白 identically
- 留白 activities are the core "breathing room" slots; giving them period-specific imagery (morning light / afternoon sun / night stars) deepens the couple experience without adding activities
- The fallback template bank ensures the experience works without an LLM key, same as M4's deterministic fallbacks

### 26. Frontend CoupleMessage Is a New Inline Component (M5)

**Decision** (2026-10-02): A new `CoupleMessage` component renders the per-activity couple note inline in `TimelineCard`, with period-differentiated accent bars (gold/blush/indigo) and a 留白 chip. `CoupleQuote` remains for day-level side display.

**Rationale**:
- `CoupleQuote` is a larger figure-style block suited for day summaries; per-activity notes need a compact inline treatment
- Period accent colors give visual rhythm at a glance: morning gold, afternoon blush, evening indigo
- 留白 cards get a dashed border + hidden cost to visually signal "this is intentional downtime, not a missing activity"
