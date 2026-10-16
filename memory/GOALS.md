## Current Iteration Goals

**Current Milestone**: V3 对话记忆与持久化（Complete，仅剩本地库初始化待执行）

**Objective**: 让 CoupleTrip 首先是一个**能正常对话**的 Agent —— 多轮记忆、真回答，
并把对话与状态**真实持久化**（刷新 / 关页 / 中断 / 多标签 / 跨天都不丢或能明确恢复）。

### V3 Completion Summary (2026-10-16)

设计与执行计划见 `UPGRADE_V3_CONVERSATION_MEMORY.md`（含 §11 设计修正与未闭环项）。

**问题起点**：`session_store.get_history()` 定义了但零调用点（历史写了从不读）、
`question` 意图回固定话术、前端只持久化 `session_id`。进一步排查发现 PostgreSQL
认证失败 + Redis 不支持 RESP3 `HELLO`，**两个持久化后端在本机全程静默降级** ——
连代码里已有的槽位记忆与行程持久化都从未真正生效。

**P0 地基**
- 双问候修复（StrictMode 双调用挂载 effect + 非幂等守卫）
- `/health` 暴露 `storage.*` 真实状态与失败原因；启动 ERROR 告警；连接失败超时 30s→5s
- 存储诊断报根因（原只报 `PoolTimeout`，掩盖了认证失败）
- 修复 E2E 全部失效（P1.3 改路由后 5 个用例仍访问 `/` 断言表单元素）

**P1 短期记忆（L0）+ 真对话**
- `ConversationStore`（PostgreSQL，`message_id` 幂等、级联删除、优雅降级）
- `acall_llm(history=...)` + `acall_llm_text()`；两段式调用：只有 question/greeting
  走第二次生成，规划类用确定性模板
- 先落 user 消息再调模型（回复前关页不丢）；会话 CRUD + `/messages` 端点
- 移除聊天链路 Redis（迁 PG 后零消费者）

**P2 长期记忆（L1/L2/L3）**
- L1 滚动摘要 + 覆盖游标，增量压缩、与旧摘要合并
- L2 跨会话画像（只增不删，冲突保留旧值并在 prompt 标注）
- L3 情节召回（历史行程 + `plan_feedback` 首次进入在线链路）
- **全部结构化存储 + SQL 召回，无 embedding**

**P3 对话恢复与前端**
- 活动会话存 sessionStorage（多标签隔离）、localStorage 存恢复种子/缓存/`client_id`
- 水合 messages/slots/planRequest；404 → 新建；末尾无回复 → "重新生成"（复用 message_id）
- 会话列表 UI（新建/切换/重命名/删除）；`storage` 事件跨标签刷新
- 会话↔行程关联（侧边栏"查看行程"）
- `npm run check:store` 零依赖 store 检查（49/49）

### Verification

- 后端 `pytest -q`：**382 passed + 2 skipped**（skip 均为 PostgreSQL 未初始化，原因显式打印）
- 前端：`npm run build` 通过（gzip 131.93 kB）+ `npm run check:store` 49/49
- 无 key / 无 PG 环境全部走 mock 与优雅降级，无 500

### Known Gaps

1. **本地 PostgreSQL 未初始化**（T0.2）：`.env` 的 `coupletrip / coupletrip_dev` 认证失败。
   幂等脚本 `backend/scripts/init_local_db.sql` 已就绪，需以超级用户执行一次。
   在此之前：PG 往返测试显式 skip（不静默通过），恢复矩阵中依赖真实库的条目未手工验证
2. **前端无组件级测试**：`check:store` 覆盖纯 store 逻辑，测不到 React effect 接线与网络
   路径；这两类由 `DEPLOY.md` 的手工冒烟清单覆盖
3. **E2E 本机不可运行**：未安装 Playwright 浏览器（T0.5 修好的用例仅在 CI 生效）
4. **多 worker 部署未支持**：`plan_streams`（SSE 队列）与限流计数是进程内存；
   需要 broker 时见 `DEPLOY.md` §七（与对话记忆无关）

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
| V3 — Conversation memory (L0–L3) + persistence & recovery | ✅ Done（T0.2 待执行） |

### Next Steps

1. **执行 `backend/scripts/init_local_db.sql`**，然后跑 `DEPLOY.md` §五 的手工冒烟清单
2. OpenTelemetry tracing（V2 唯一跳过项：LLM + 外部 API span）
3. 多用户协作编辑（需要 WebSocket）
4. 更多目的地 / 离线缓存 PWA / 真实支付

### Blockers

无代码阻塞。唯一外部依赖：本地 PostgreSQL 需要超级用户执行一次初始化脚本。

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

### V2 Verification

- 后端 `pytest -q`：**267 passed + 1 skipped**（`backend/.venv` 实测；P1.2 收口新增 30 个测试，此前 237）
- 前端：`npm run build`（`tsc -b && vite build`）通过 — 2263 modules transformed，产物 gzip 128.81 kB
- 无 key / 无 PG / 无 Redis 环境全部走 mock 与优雅降级，无 500

### V2 Known Gaps

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

### M7 Verification

- `npm run build` (`tsc -b && vite build`) — passed after sse.ts fix
- Backend: 183 passed + 1 skipped (unchanged, no backend changes in M7)
- E2E & backend pytest require runtime environment; CI pipeline runs automatically on push
