## Current Iteration Goals

**Current Milestone**: V2 升级 P0–P3（Complete）— 地基修复 / 对话式 / 内容质量 / 工程化

**Objective**: 兑现文档承诺的行程持久化，解决并发与断线重连的正确性问题，把产品从固定表单推进到对话式，并达到生产门槛（鉴权、限流、可观测性、外部 API 韧性）。

### V2 Completion Summary (2026-10-14 → 2026-10-16)

V2 升级完成。方案依据 `UPGRADE_V2_AUDIT.md`（企业级视角重排优先级），任务清单见 `UPGRADE_V2_EXECUTION_PLAN.md`。

**P0 地基修复（2026-10-14）**
- 行程持久化：PostgreSQL(`postgres:16-alpine`) + `services/storage.py` `PlanStore`（JSONB / 连接池 / DDL 幂等 / PG 不可达时优雅降级）；补齐 `GET /api/plan/{id}`、`GET /api/plan/history`、`DELETE /api/plan/{id}`；`/result?plan_id=xxx` 刷新可恢复
- LLM 异步化：新增 `acall_llm()`（`llm.ainvoke()`），10 个节点全部 `async def`，不再占线程池阻塞事件循环
- SSE 重连不重跑：`POST /api/plan` 返回 `{plan_id, stream_url}` 后台投递，新增 `GET /api/plan/{id}/stream`；重连同一流而非重跑整条 LangGraph 管线

**P1 对话式（2026-10-14 → 2026-10-16）**
- 后端：`POST /api/chat` + Redis 会话（`redis.asyncio`，TTL 30min，跨 worker/刷新可续聊）+ 槽位确定性后处理（相对日期、预算单位归一）
- 前端：`Chat` 页 + `ChatWindow`/`ChatInput`/`SlotPanel`，`/` → Chat、`/form` 保留旧表单
- `modify_plan` 增量调整：识别"预算加到8千""再加一天"等修改意图，patch 合并回槽位并重置 ready，前端据此更新 `planRequest`

**P2 内容质量（2026-10-14，替代原 M10 pgvector）**
- `_couple_score` 重写为 rating 0.5 + 类型偏好 0.3 + 季节适配 0.2，真实评分主导
- `data/curated_pois.json` 人工精选（大理/三亚/杭州/成都/厦门）优先于 Amap 结果
- 用户反馈闭环：👍/👎 写入 PostgreSQL + `scripts/recompute_scores.py` 离线重算

**P3 工程化（2026-10-15）**
- 鉴权 + 限流：`X-API-Key` 校验（`deps.py`）+ `slowapi`（`/api/plan` 10/min、`/api/chat` 30/min）
- 可观测性：`structlog` JSON 日志 + `/metrics`（Prometheus）+ `complete` 事件 `degraded` 标志
- 配置规范化：`pydantic-settings.BaseSettings` + `.env.dev`/`.env.prod` 分层 + CORS 从 env 读
- 外部 API 韧性：Amap/QWeather 指数退避重试 3 次 + 熔断器（连续失败 5 次短路 30s）

### Verification

- 后端 `pytest -q`：**267 passed + 1 skipped**（`backend/.venv` 实测；P1.2 收口新增 30 个测试，此前 237）
- 前端：`npm run build`（`tsc -b && vite build`）通过 — 2263 modules transformed，产物 gzip 128.81 kB
- 无 key / 无 PG / 无 Redis 环境全部走 mock 与优雅降级，无 500

### Known Gaps

- **P3.2.3 OpenTelemetry tracing 未做**（本轮明确跳过，只交付 structlog + metrics）；LLM 与 Amap/QWeather 调用暂无 span，需要时按 `UPGRADE_V2_EXECUTION_PLAN.md` T3.2.3 补
- `backend/.venv` 需保持 `pip install -r requirements.txt` 同步，否则 V2 依赖缺失会导致 pytest 直接 collection error

### M7 Completion Summary (2026-10-03)

M7 is complete. All 8 milestones delivered. Delivered:
- Docker: `backend/Dockerfile` (python:3.13-slim), `frontend/Dockerfile` (multi-stage node→nginx), `nginx.conf` (SPA + `/api` reverse proxy + SSE no-buffer)
- Docker Compose: production version with healthcheck + `depends_on: service_healthy` + restart policy
- CI: `.github/workflows/ci.yml` three-stage pipeline (backend-test → frontend-build → docker-build)
- E2E: `frontend/e2e/full_flow.spec.ts` 5 scenarios via Playwright (chromium)
- Docs: `memory/DEPLOY.md` — local dev / Docker deploy / E2E / CI / delivery checklist
- Bug fix: `frontend/src/services/sse.ts` `MessageEvent` naming conflict resolved (was blocking `tsc -b` build)

### Verification

- `npm run build` (`tsc -b && vite build`) — passed after sse.ts fix
- Backend: 183 passed + 1 skipped (unchanged, no backend changes in M7)
- E2E & backend pytest require runtime environment; CI pipeline runs automatically on push

### All Milestones

| Milestone | Status |
|-----------|--------|
| M0 — Project scaffold | ✅ Done |
| M1 — Agent engine | ✅ Done |
| M2 — External API integration | ✅ Done |
| M3 — Frontend UI | ✅ Done |
| M4 — Budget + weather | ✅ Done |
| M5 — Rhythm + couple experience | ✅ Done |
| M6 — SSE streaming | ✅ Done |
| M7 — Testing + deployment | ✅ Done |
| V2-P0 — Foundation (persistence / async LLM / SSE reconnect) | ✅ Done |
| V2-P1 — Conversational (Redis chat + Chat UI + modify_plan) | ✅ Done |
| V2-P2 — Content quality (couple_score + curated + feedback) | ✅ Done |
| V2-P3 — Production (auth / rate limit / observability / resilience) | ✅ Done |

### Next Steps (future iteration, not planned)

1. OpenTelemetry tracing（V2 唯一跳过项：LLM + 外部 API span）
2. Multi-user collaborative itinerary editing (would require WebSocket)
3. More destinations beyond the current curated city list
4. Offline cache / PWA support
5. Real payment integration for booking

### Blockers

None — M0–M7 与 V2 P0–P3 均已交付；已知缺口见上方 Known Gaps。
