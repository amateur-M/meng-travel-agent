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



### 8. Graph Topology: Conditional Edge for Budget Retry

**Decision**: budget_check → plan_itinerary uses a conditional edge (not a fixed loop).

**Rationale**:
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
- Once a downgrade is applied, `_route_after_budget` routes straight to `adapt_weather` so regenerating the draft does not undo the savings
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
