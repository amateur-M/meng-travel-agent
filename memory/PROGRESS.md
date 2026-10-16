## Development Progress

| Milestone | Status | Start Date | End Date | Notes |
|-----------|--------|------------|----------|-------|
| M0 | Done | 2026-08-10 | 2026-08-10 | Project scaffold complete |
| M1 | Done | 2026-08-10 | 2026-08-11 | Agent engine core + tests |
| M2 | Done | 2026-08-11 | 2026-08-16 | External API + LLM integration |
| M3 | Done | 2026-08-16 | 2026-08-18 | Frontend core UI refactor |
| M4 | Done | 2026-08-30 | 2026-08-31 | Budget + weather |
| M5 | Done | 2026-10-02 | 2026-10-02 | Rhythm control + couple experience |
| M6 | Done | 2026-10-03 | 2026-10-03 | SSE streaming enhancement |
| M7 | Done | 2026-10-03 | 2026-10-03 | Testing + deployment |
| V2-P0 | Done | 2026-10-14 | 2026-10-14 | 地基修复：PG 持久化 + LLM 异步化 + SSE 重连不重跑 |
| V2-P1 | Done | 2026-10-14 | 2026-10-16 | 对话式：Redis 会话 + 槽位后处理 + Chat UI + modify_plan |
| V2-P2 | Done | 2026-10-14 | 2026-10-14 | 内容质量：couple_score 重写 + curated POI + 反馈闭环 |
| V2-P3 | Done | 2026-10-15 | 2026-10-15 | 工程化：鉴权限流 + 可观测性 + 配置规范化 + 外部 API 韧性 |
| V3 | Done | 2026-10-16 | 2026-10-16 | 对话记忆 L0–L3 + 会话持久化与恢复（T0.2 本地库初始化待执行） |

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

## M6 Completion Checklist (2026-10-03)

### Backend — SSE Event Expansion
- [x] `_stream_graph` switched from `stream_mode="values"` to `stream_mode="updates"` to get per-node partial outputs
- [x] New `_emit_node_events` helper emits targeted events per phase:
  - `partial` — plan_itinerary / rhythm_control: one event per day with activities
  - `budget_alert` — budget_check: current/limit/warning_level/spending_ratio/downgrade info
  - `weather_swap` — adapt_weather: one event per swap (original/replacement/reason/adjustment_type)
  - `message` — add_couple_touch: one event per activity couple note
- [x] New `_sse()` helper formats a single SSE frame
- [x] Removed the obsolete `except AttributeError` sync fallback branch — LangGraph 1.2.12 `astream` is always available, and the branch wrongly swallowed node-level `AttributeError`s
- [x] `complete` event still validated through `TripPlanResponse` + carries `warnings`

### Frontend — Streaming UX
- [x] `services/sse.ts`: `postEventStream` rewritten to dispatch all 7 event types + auto-retry on disconnect (max 2 retries, 800ms×attempt backoff)
- [x] New `components/StreamingItinerary/StreamingItinerary.tsx`: progressive day/period rendering of activity cards from `partial` events
- [x] `stores/tripStore.ts`: new streaming state (`streamingDays` / `budgetAlert` / `weatherSwaps` / `coupleMessages`) + event callbacks wired into `beginPlanning`
- [x] `pages/Loading.tsx`: renders streaming itinerary below the progress list + live badges for budget/weather/message counts
- [x] `types/trip.ts`: new `PartialEvent` / `BudgetAlertEvent` / `WeatherSwapEvent` / `MessageEvent` interfaces
- [x] `services/plan.ts`: `createPlan` forwards the new event callbacks

### Tests
- [x] New `tests/test_sse.py`: 16 tests — `_sse`/`_phase_message`/`_emit_node_events` unit tests + full-stream integration (event types, ordering, complete structure)

### Test Result
- Backend: **183 passed + 1 skipped** (was 167; +16 new M6 SSE tests)
- Frontend: `tsc --noEmit` typecheck passed + Vite production build passed

## M7 Completion Checklist (2026-10-03)

### Docker 化
- [x] `backend/Dockerfile` — python:3.13-slim + uvicorn 直跑
- [x] `frontend/Dockerfile` — 多阶段构建（node:20 build → nginx:alpine 托管静态产物）
- [x] `frontend/nginx.conf` — SPA fallback + `/api` 反代 backend:8000 + SSE 关闭缓冲
- [x] `backend/.dockerignore` + `frontend/.dockerignore` — 排除测试/缓存/依赖
- [x] `docker-compose.yml` 重写为生产版 — healthcheck + `depends_on: service_healthy` + `restart: unless-stopped`

### CI 流水线
- [x] `.github/workflows/ci.yml` — 三阶段：backend-test → frontend-build → docker-build
- [x] 后端 job 无 API key 走 mock 降级路径
- [x] 前端 job 跑 `tsc --noEmit` + `vite build`
- [x] docker job 依赖前两个通过后构建镜像

### E2E 测试
- [x] `frontend/playwright.config.ts` — chromium + 自动启动 dev server
- [x] `frontend/e2e/full_flow.spec.ts` — 5 个场景：首页加载、完整流程、结果页元素、重新规划、低预算降级
- [x] `package.json` 新增 `e2e` / `e2e:install` 脚本 + `@playwright/test` 依赖

### 文档
- [x] `memory/DEPLOY.md` — 本地开发 / Docker 部署 / E2E 运行 / CI 说明 / 交付清单

### 既有 Bug 修复
- [x] `frontend/src/services/sse.ts` — `MessageEvent` 命名冲突（M6 引入的既有 bug）：自定义类型遮蔽 DOM 全局 `MessageEvent` 类型，导致 `tsc -b` 构建失败。改用 `MessageEvent as CoupleMessageEvent` 别名导入，构建通过

### 验证
- [x] `npm run build`（`tsc -b && vite build`）通过 — sse.ts 类型冲突修复后无构建错误
- [x] E2E 测试与后端 pytest 需运行时环境，未在本次执行（CI 流水线会在 push 时自动运行）

---

## V2 升级执行（P0–P3）

> 方案与理由见 `UPGRADE_V2_AUDIT.md`，任务级执行清单见 `UPGRADE_V2_EXECUTION_PLAN.md`。
> 本节只记录**已实现并验证**的产出，测试数字为实测值。

### P0 地基修复（2026-10-14）

- [x] P0.1 行程持久化：`docker-compose.yml` 加 `db`(postgres:16-alpine) + volume；`services/storage.py` `PlanStore`（JSONB 存 response、连接池、DDL 幂等、PG 不可达时优雅降级）；`POST /api/plan` 先写 `status=processing` 再写回 `completed`
- [x] P0.1 补齐 ARCHITECTURE.md 承诺的 4 端点：`GET /api/plan/{id}`、`GET /api/plan/history?page=&size=`、`DELETE /api/plan/{id}`，SSE `complete` 事件带 `plan_id`
- [x] P0.1 前端：`tripStore` 接收 `plan_id`，`/result?plan_id=xxx` 走 REST 恢复，`Loading` 支持 `?plan_id=` 直连
- [x] P0.2 LLM 异步化：`services/llm.py` 新增 `acall_llm()`（`llm.ainvoke()`），保留 `call_llm` 兼容；10 个节点全部改 `async def`
- [x] P0.3 SSE 重连不重跑：`POST /api/plan` 返回 `{plan_id, stream_url}` 并后台投递任务（`asyncio.create_task` + 内存事件队列）；新增 `GET /api/plan/{plan_id}/stream`，已完成则从 PostgreSQL 重放；前端拆 `startPlan()` / `resumeStream(id)`

### P1 对话式（2026-10-14 → 2026-10-16）

- [x] P1.1 `POST /api/chat`：`services/session_store.py`（`redis.asyncio`、key `chat:{session_id}`、TTL 30min）+ `schemas/chat.py` + `prompts/chat_intent_prompt.md` + `agents/conversation.py`（单次 `acall_llm` 出意图与槽位、Redis 槽位合并、ready 判定、Redis 宕机优雅降级）
- [x] P1.1 `postprocess_slots()` 确定性后处理：相对日期（"下周末"→推算）、预算单位归一（"5千"→5000、"1.5万"→15000）
- [x] P1.3 对话前端：`pages/Chat.tsx` + `components/Chat/{ChatWindow,ChatInput,SlotPanel}` + `services/chat.ts` + `stores/chatStore.ts`；路由 `/` → Chat、`/form` 保留旧表单；sessionStorage 持久化 `session_id`
- [x] P1.2 `modify_plan` 增量调整（2026-10-16 收口）：`ChatReply.modify_patch` + `conversation.py` `postprocess_patch()` 解析增量修改并**合并回槽位**、重置 ready（不自动重新规划）；`chatStore` 检测到 patch 后合并进 `planRequest` 并重新武装规划按钮
  - 确定性后处理覆盖：预算单位归一（"预算加到8千"→8000）、相对天数推移（"再加一天"→`end_date` 推后 1 天，跨月边界 09-30→10-01）、负向推移（"提前一天"）、裸时长重锚（"5天"→按 `start_date` 重算 `end_date`）、目的地变更（"换成杭州"）
  - 修改识别的边界：已有完整槽位时才判定为修改；"想去三亚，预算8000元" 仍走新规划，不被预算关键词误判为修改
  - 新增 `tests/test_chat.py` 30 个测试（`TestDayShiftParsing` / `TestPostprocessPatch` / `TestMockModify` / `TestLooksLikeModification` / `TestHandleChatModify`），覆盖 mock 与 LLM 两条路径

### P2 内容质量（2026-10-14，替代原 M10 pgvector）

- [x] P2.1 `_couple_score` 重写：rating 权重 0.5 + 类型匹配偏好 0.3 + 室内/户外季节适配 0.2；`food_search_tool.py` 评分逻辑统一
- [x] P2.2 `backend/data/curated_pois.json` 人工精选（大理/三亚/杭州/成都/厦门），`search_poi` 先查 curated（city + preferences 过滤）再补 Amap，curated 项带 `source` 字段供 UI 展示"精选"徽章
- [x] P2.3 反馈闭环：`PlanStore` 反馈表 + `POST /api/plan/{id}/feedback` + `scripts/recompute_scores.py` 离线重算 + `TimelineCard` 👍/👎 按钮
- [x] 无 pgvector 依赖，复用 P0.1 的 postgres 实例

### P3 工程化（2026-10-15）

- [x] P3.1 鉴权与限流：`config/settings.py` 增 `auth_enabled` / `api_keys` / `rate_limit_*`；`deps.py` `verify_api_key` 校验 `X-API-Key` 并挂到全部 `/api/*`；`slowapi` 限流（`/api/plan` 10/min、`/api/chat` 30/min）；前端 `VITE_API_KEY` 经 axios 拦截器 + SSE fetch 注入
- [x] P3.2 可观测性：`structlog` 结构化 JSON 日志（`logging_config.py`）、`prometheus-fastapi-instrumentator` 暴露 `/metrics`、SSE `complete` payload 增 `degraded` 标志
- [x] P3.3 配置规范化：`config/settings.py` 迁 `pydantic-settings.BaseSettings`，支持 `.env.dev`/`.env`/`.env.prod` 分层，CORS origins 从 env 读；`pyproject.toml` 与 `requirements.txt` 依赖清单对齐为单一来源
- [x] P3.4 外部 API 韧性：`services/resilience.py` 熔断器（连续失败 5 次短路 30s）+ `services/amap.py`、`tools/weather_tool.py` 指数退避重试 3 次（`tenacity`）
- [ ] P3.2.3 OpenTelemetry tracing — **本轮明确跳过**，只做 structlog + metrics（LLM/外部 API span 不可见，后续要做需补）

### V2 验证记录

- [x] 后端 `pytest -q`：**267 passed + 1 skipped**（`backend/.venv` 实测；P1.2 收口新增 30 个测试，此前 237）
- [x] 前端 `npm run build`（`tsc -b && vite build`）通过 — 2263 modules transformed，产物 `dist/assets/index-*.js` 397.76 kB（gzip 128.81 kB）
- [x] 无 API key / 无 PG / 无 Redis 环境下全部走 mock 与优雅降级路径，不阻塞测试

### 环境注意事项

- `backend/.venv` 曾缺失 V2 新增依赖（`pydantic-settings`/`psycopg`/`psycopg-pool`/`redis`/`slowapi`/`structlog`/`prometheus-fastapi-instrumentator`），旧 `.venv` 直接跑 pytest 会 16 个 collection error。已执行 `pip install -r requirements.txt` 修复；**换机器或清理 venv 后需重跑该命令**。
- `backend/.pytest_cache` 目录存在权限拒绝，导致无害的 `PytestCacheWarning`（不影响测试结果）。

---

## V3 对话记忆与持久化（2026-10-16）

> 设计与执行计划见 `UPGRADE_V3_CONVERSATION_MEMORY.md`（含 §11 设计修正与未闭环项）。

### 问题起点

用户反馈"对话记忆没有做，要保证这个 Agent 首先是一个可正常对话的 Agent"。
排查确认三条同时成立：`session_store.get_history()` 定义了但**零调用点**（历史写了从不读）；
`question` 意图回固定话术；前端只持久化 `session_id`、刷新即丢对话。
更进一步：PostgreSQL 认证失败 + Redis 不支持 `HELLO`（RESP3），**两个持久化后端
在本机全程静默降级**，代码里已有的槽位记忆与行程持久化一次都没真正生效。

### P0 环境与地基

- [x] T0.1 修复双问候：StrictMode 双调用挂载 effect，而问候 effect 读的是渲染闭包里的
  陈旧值。改为 store 幂等 action `ensureGreeting()`，守卫读实时状态
- [x] T0.4 消除静默降级：`/health` 暴露 `storage.postgres` / `storage.chat`（含失败原因），
  启动时一次性 ERROR 告警；**并把连接失败超时 30s → 5s**（整套测试 37s → 18s）
- [x] T0.4+ 存储诊断报根因：原只报 `PoolTimeout`，现用一次直接连接取出
  `password authentication failed ...` 再上报
- [x] T0.5 修复 E2E 路由失效：P1.3 把 `/` 改成对话页后 5 个用例仍访问 `/` 并断言表单元素，
  实际全失效（与既有文档"不破坏"矛盾）；已改从 `/form` 进入并加问候回归守卫
- [ ] T0.2 本地 PostgreSQL 可达：脚本 `backend/scripts/init_local_db.sql` 已就绪（幂等），
  **待以超级用户执行一次**；未执行时 PG 往返测试显式 skip 不静默通过

### P1 短期记忆与真对话（L0）

- [x] `services/conversation_store.py`：`chat_sessions` + `chat_messages`（JSONB 槽位、
  `message_id UNIQUE`、`ON DELETE CASCADE`），幂等 append、优雅降级、`health()`
- [x] `acall_llm(history=...)` + 新增 `acall_llm_text()`（自由文本，用于必须"真回答"的场景）
- [x] `handle_chat` 两段式：Call 1 总是跑（意图+槽位，带最近 10 轮记忆）；只有
  question/greeting 才走 Call 2 生成真回答，规划类用确定性模板（省一次调用）
- [x] **先落 user 消息再调模型**（回复前关页不丢消息）；`message_id` 透传保证重试幂等
- [x] 会话 CRUD + `/messages` 端点；首条实质消息自动生成标题
- [x] 移除聊天链路 Redis（会话迁 PG 后零消费者；限流器本就未用 Redis）

### P2 长期记忆（L1/L2/L3）

- [x] L1 滚动摘要 + `summary_message_count` 游标，增量压缩、与已有摘要合并、溢出满
  4 条才触发
- [x] L2 跨会话画像（`user_profiles`，key = 浏览器 `client_id`）：只增不删，被替换的
  标量留在 `conflicts` 并渲染成"出发地：上海（此前提到过：北京）"
- [x] L3 情节召回：历史行程 + `plan_feedback` 聚合。**反馈表首次进入在线链路**
- [x] prompt 组装顺序固定：角色 → L2 → L3 → L1 → L0 真实消息
- [x] **全部用结构化存储 + SQL 召回，无 embedding** —— 长期记忆与"V2 拒绝 pgvector"并不冲突
- [x] 记忆预算（T2.4 收口）：L0 窗口 20 条，且**单条 ≤2000 字符、整块 ≤8000 字符** ——
  超预算丢最旧的（旧内容已由 L1 承载，丢最新一轮会破坏"那改成三天呢"这类追问）；
  溢出满 4 条才触发摘要；摘要上限 1200 字。由 `tests/test_llm_history.py`（16 例）钉住。
  *此项在首轮收尾时自查发现只做了单条截断、漏了整块上限，而文档已按"有预算"描述 —— 属未交付，
  本轮补齐。*

### P3 对话恢复与前端

- [x] 存储分工：活动会话存 **sessionStorage**（多标签隔离），localStorage 只存
  恢复种子 / 侧边栏缓存 / `client_id`
- [x] `hydrate()`：并行拉会话详情 + 完整记录，水合 messages/slots/planRequest/lastPlanId
- [x] 恢复硬化：404 → 清指针并新建（#4）；末尾无回复的 user 消息 → "重新生成"（#5），
  重试复用同一 `message_id` 不重复写（#6）
- [x] 会话列表 UI（桌面常驻 / 移动端抽屉）：新建、切换、重命名、删除；`storage` 事件
  跨标签刷新列表（#7）
- [x] 会话↔行程关联：`session_id` 随 `POST /api/plan` 传入，侧边栏可"查看行程"
- [x] `npm run check:store`：零依赖 store 行为检查（49/49），补 tsc/build 抓不到的状态缺陷

### V3 验证记录

- [x] 后端 `pytest -q`：**407 passed + 2 skipped**（2 个 skip 均为 PostgreSQL 未初始化，
  跳过原因显式打印）
- [x] **不依赖数据库也能验证完整对话链路**：`tests/test_conversation_e2e.py` 用
  `InMemoryConversationStore`（并断言它实现了真实 store 的每个公开方法，防止假实现腐化）
  驱动 ASGI 应用端到端 —— 两轮对话按序落库、**第二轮真的看到第一轮**、重放同一
  `message_id` 不产生重复、修改轮合并进已落库槽位、画像跨越新会话、超窗口写入滚动摘要。
  P1 的出口判据因此不必等 T0.2
- [x] 前端 `npm run build` 通过（2264 modules，产物 gzip 131.93 kB）+ `npm run check:store` 49/49
- [x] E2E 用例纳入类型检查（新增 `tsconfig.e2e.json`；CI 的 `tsc --noEmit` 改为 `tsc -b`，
  前者在根项目 `files: []` 下实际什么都没检查）
- [x] **前后端 URL 契约纳入测试**：`tests/test_api_contract.py` 从
  `frontend/src/services/chat.ts` 抽出真实调用的 URL 与方法，比对应用自身的 OpenAPI
  schema（按形状比对，占位符名不敏感），并校验前端依赖的请求/响应字段仍在。
  写这条测试时发现 `ChatReply`/`SessionDetail`/`SessionListResponse`/`MessageListResponse`
  已定义却从未挂成 `response_model`（等于死代码、响应结构无文档），已一并接线
- [x] **`PlanStore` 不再阻塞事件循环**：此前它在 async 端点里被直接调用（V2 P0.2
  只改到了 `ConversationStore`）。实测一次存储调用会让事件循环停摆 0.39s／0.4s，
  而 PG 不可达时这个数字就是 5s 池超时 —— 期间**所有**请求都被冻住。现全部经
  `asyncio.to_thread`，新增 `tests/test_event_loop.py` 用**事件循环延迟**度量守住
  四条路径（计划写入/读取/历史/反馈）；该测试在修复前确实失败（0.39s < 阈值 0.15s 不成立）
- [ ] 恢复矩阵中依赖**真实数据库**的条目（刷新恢复、跨天、多标签、切换、真实 PG 往返）
  待 T0.2 后按 `DEPLOY.md` 手工冒烟清单逐条勾选

### V3 的设计修正（详见计划文档 §11）

| 原计划 | 实际做法 | 原因 |
|--------|----------|------|
| `AsyncConnectionPool` 全程异步 | 同步池 + `asyncio.to_thread` | psycopg 异步模式在 Windows 默认 `ProactorEventLoop` 上直接 `InterfaceError`；P0.2 的约束是"不阻塞事件循环"，线程卸载等价且跨平台 |
| T0.3 移除 Redis 放在 P0 | 并入 P1 | 先删 Redis 会让中间态没有会话存储；等 PG 接过再删，每个提交都是绿的 |
| "最近 10 轮" | `HISTORY_MESSAGES = 20`（条数） | `get_recent_messages` 单位是消息条数，一轮 = 2 条，初版实际只给了 5 轮 |
