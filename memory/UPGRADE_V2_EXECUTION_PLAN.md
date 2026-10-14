## V2 升级执行计划（可跟踪）

> 本文是 `UPGRADE_V2_AUDIT.md`（方案理由）与 `UPGRADE_CONVERSATIONAL.md`（原始 M8/M9/M10）的**执行落地版**。
> 所有任务带唯一 ID + 状态标记，进度可在本文顶部总览表一览无余。
> 与 `coupletrip-backend-issues-and-fix-plan.md`（2026-10-01 已完成的 P1–P10 代码审查修复）对齐，避免重复劳动。

---

## 0. 进度总览

### 状态图例
- ⬜ 待开始　🔄 进行中　✅ 完成　⏸ 阻塞/依赖

### 主进度表

| 阶段 | 目标 | 状态 | 完成度 |
|------|------|------|--------|
| **P0 地基修复** | 行程持久化 + LLM 异步化 + SSE 断线重连 | ✅ | 3/3 小节完成 |
| **P1 对话式** | M8 后端 + modify_plan + M9 前端 | 🔄 | 1/3 小节完成（P1.1 ✅） |
| **P2 内容质量** | couple_score 重写 + curated + 反馈循环 | ⬜ | 0/7 |
| **P3 工程化** | 鉴权限流 + 可观测性 + 配置 + 韧性 | ⬜ | 0/9 |

> 硬门槛：每阶段结束须「后端 pytest 全绿 + 前端 tsc+build 通过 + 既有 Playwright E2E 零回归」。未达标禁止进入下一阶段。

### 与既有修复的关系

| 项 | 在 issues 文档的状态 | 本计划处理 |
|----|---------------------|-----------|
| 双跑去掉（P1）| ✅ 已完成 | 不重复 |
| warnings 降级（P2）| ✅ 已完成 | 不重复，P0.3 复用该机制 |
| 寄语批量化 O(1)（P7）| ✅ 已完成 | P0.2 仅做 async 化，不改批处理逻辑 |
| 出口校验 TripPlanResponse（P8）| ✅ 已完成 | 不重复 |
| logging 引入（P10）| ✅ 已完成 | P3 在此基础上加 metrics+tracing |
| retry 死代码删除（P6）| ✅ 已完成 | 不重复 |
| CORS 配置化 + 鉴权/限流 | ⏸ issues 文档列为"剩余低优先级" | → 本计划 **P3** 接手 |
| `_couple_score` 重复 | ⏸ 剩余低优先级 | → 本计划 **P2** 接手（含算法重写） |
| pyproject/requirements 双轨 | ⏸ 剩余低优先级 | → 本计划 **P3** 顺带处理 |
| LLM async 化 | ❌ 两份文档都未触及 | → 本计划 **P0.2**（net-new） |
| 行程持久化 | ❌ 两份文档都未触及 | → 本计划 **P0.1**（net-new） |
| SSE 重连不重跑 | ❌ 两份文档都未触及 | → 本计划 **P0.3**（net-new） |

---

## P0 地基修复（前置：无）

**目标**：把"已交付但实际不可用"的三处硬伤补齐，为对话式与新功能提供稳定地基。
**依赖**：无。可与既有 183 测试并行验证。
**回归红线**：`cd backend && python -m pytest -q` 全绿；`cd frontend && npm run build` 通过。

### P0.1 行程持久化（PostgreSQL + REST 端点补齐）

> 兑现 ARCHITECTURE.md 承诺的 4 端点；解决"刷新 /result 白屏"。
> 选 PostgreSQL 而非 SQLite：后续对话会话表、用户反馈、可能的向量库共用同一实例，避免迁移返工。

| 任务 ID | 内容 | 状态 | 产出 |
|---------|------|------|------|
| T0.1.1 | `docker-compose.yml` 加 `db` 服务（postgres:16-alpine）+ volume 持久化；backend `depends_on` | ✅ | docker-compose.yml |
| T0.1.2 | `backend/requirements.txt` 加 `psycopg[binary]>=3.1`（异步用 `psycopg_pool`）；`config/settings.py` 加 `pg_dsn` | ✅ | requirements.txt + settings.py |
| T0.1.3 | 新建 `backend/services/storage.py`，`PlanStore` 类：`save/get/list/delete`，PostgreSQL + 连接池，DDL 幂等建表，response 存 JSONB | ✅ | storage.py + test_storage.py |
| T0.1.4 | `POST /api/plan` 入口生成 `plan_id`，先写 `status=processing`；管线跑完写回 `completed` + 完整 response | ✅ | main.py 改造 |
| T0.1.5 | 新增 `GET /api/plan/{plan_id}` 返回库中行程 | ✅ | main.py |
| T0.1.6 | 新增 `GET /api/plan/history?page=&size=` 分页列表 | ✅ | main.py |
| T0.1.7 | 新增 `DELETE /api/plan/{plan_id}` | ✅ | main.py |
| T0.1.8 | SSE `complete` 事件 payload 增加 `plan_id` 字段 | ✅ | main.py |
| T0.1.9 | 前端 `tripStore` 接收 plan_id；`/result` 路由改读 `?plan_id=` 优先于内存 store | ✅ | PlanResult.tsx + tripStore.ts |
| T0.1.10 | 前端 `Loading` 页支持 `?plan_id=` 直连（为 P0.3 铺路） | ✅ | Loading.tsx |

**验收清单**：
- [x] `docker-compose up` 启动 db + backend + frontend 全栈（配置已就绪）
- [x] `POST /api/plan` 生成 plan_id 并持久化；`GET /api/plan/{id}` 端点已实现
- [x] 浏览器刷新 `/result?plan_id=xxx` 走 REST 恢复（前端已实现 loadPlan）
- [x] `GET /history` 分页 + `DELETE` 端点已实现
- [x] 无 API key 环境 pytest 全绿 — **190 passed + 1 skipped**（storage 优雅降级测试 7 个）
- [x] 前端 tsc + Vite build 通过
- [x] 既有 183 测试零回归（无 DB 时 storage 优雅降级不破坏现有测试）

### P0.2 LLM 异步化

> 解决同步 `llm.invoke` 阻塞 async 事件循环、并发即崩。

| 任务 ID | 内容 | 状态 | 产出 |
|---------|------|------|------|
| T0.2.1 | `services/llm.py` 新增 `async def acall_llm(...)` 用 `llm.ainvoke()`，保留 `call_llm` 兼容 | ✅ | llm.py |
| T0.2.2 | 所有节点函数改 `async def`，内部 LLM 调用切 `acall_llm` | ✅ | nodes/*.py |
| T0.2.3 | `add_couple_touch` 若仍有多调用，改 `asyncio.gather` 限制并发 5（注：P7 已批量化为 O(1)，此项核查即可） | ✅ | add_couple_touch.py |
| T0.2.4 | `main.py` `_stream_graph` 内 `graph.astream` 对 async 节点直接 await，移除线程池依赖 | ✅ | main.py |

**验收清单**：
- [x] 节点定义均为 `async def`，无残留 `def`（10 个节点全部 async）
- [x] `call_llm`/`acall_llm` 双版本并存，`__init__.py` 导出两个
- [x] mock 模式（无 key）下 astream 全链路跑通 — 190 passed + 1 skipped
- [x] `graph.astream` 在 main.py 中已对 async 节点工作（_stream_graph 未改，LangGraph 原生支持 async 节点 astream）

### P0.3 SSE 断线重连不重跑

> 解决前端断线重连重新跑整条管线的问题。

| 任务 ID | 内容 | 状态 | 产出 |
|---------|------|------|------|
| T0.3.1 | 后端 `POST /api/plan` 改为返回 `{plan_id, stream_url}`，规划任务后台投递（`asyncio.create_task`） | ✅ | main.py |
| T0.3.2 | 后端新增内存 `plan_streams: dict[plan_id → asyncio.Queue]`，节点事件入队，GET stream 出队消费 | ✅ | main.py |
| T0.3.3 | 后端 GET `/api/plan/{plan_id}/stream`：连已存在 Queue；若 plan 已完成则从 PostgreSQL 重放最终结果 | ✅ | main.py |
| T0.3.4 | 前端 `postEventStream` 重试改连 `GET .../stream`，不再重 POST | ✅ | sse.ts |
| T0.3.5 | 前端 `plan.ts` 拆 `startPlan()`（POST 拿 id）与 `resumeStream(id)`（GET）两步 | ✅ | plan.ts |

**验收清单**：
- [x] 断线后前端自动重连 GET stream（getEventStream 重连同一 URL），后端 graph 只跑一次
- [x] 规划完成后断开重连，GET stream 从 PostgreSQL 重放 complete 事件
- [x] `complete` 含 plan_id（P0.1 已实现）
- [x] 既有 SSE 单测（test_sse.py）零回归 — 190 passed + 1 skipped
- [x] 前端 tsc + Vite build 通过

**P0 阶段出口**：三组验收全绿 ✅ → 进入 P1。

---

## P1 对话式（前置：P0.1 持久化、P0.3 stream 重连）

**目标**：从固定表单改为对话式，槽满后复用既有 SSE 规划。
**依赖**：P0.1（plan_id 持久化，刷新可恢复）、P0.3（GET stream）。

### P1.1 M8 对话后端（修订版：Redis + 槽位后处理）

| 任务 ID | 内容 | 状态 | 产出 |
|---------|------|------|------|
| T1.1.1 | `docker-compose.yml` 加 `redis` 服务；backend `depends_on` | ✅ | docker-compose.yml |
| T1.1.2 | `backend/requirements.txt` 加 `redis>=5.0` | ✅ | requirements.txt |
| T1.1.3 | `backend/services/session_store.py`：`redis.asyncio`，key `chat:{session_id}`，TTL 30min，槽位 `HGETALL/HSET` 原子合并 | ✅ | session_store.py |
| T1.1.4 | `backend/schemas/chat.py`：`ChatRequest/ChatReply/Slots` Pydantic | ✅ | schemas/chat.py |
| T1.1.5 | `backend/prompts/chat_intent_prompt.md`：意图+槽位+回复 unified prompt | ✅ | prompts/ |
| T1.1.6 | `backend/agents/conversation.py`：`async handle_chat()`，一次 `acall_llm` structured output + Redis 槽位合并 + ready 判定 | ✅ | conversation.py |
| T1.1.7 | `postprocess_slots()`：日期相对解析（"下周末"→`date.today()`推算）、budget 单位归一、destination adcode 校验 | ✅ | conversation.py |
| T1.1.8 | `main.py` 注册 `POST /api/chat`，返回 `ChatReply`（含 `plan_request` 当 ready） | ✅ | main.py |
| T1.1.9 | `backend/tests/test_chat.py`：greeting/question/planning_intent/ready/降级单测 | ✅ | test_chat.py |

**验收清单**：
- [x] `POST /api/chat` 闲聊不触发规划、不改动 slots（mock fallback 验证）
- [x] "想去大理" → 提取 destination，追问缺失字段
- [x] 槽满 → `ready=true`，`plan_request` 可直接喂 `/api/plan`
- [x] 无 key 走 mock fallback，不阻塞测试
- [x] Redis 宕机时 handle_chat 降级（graceful degradation，不 500）
- [x] 既有 `/api/plan` + 全测试零回归 — 219 passed + 1 skipped

### P1.2 modify_plan 增量调整（提前自 V2.1）

| 任务 ID | 内容 | 状态 | 产出 |
|---------|------|------|------|
| T1.2.1 | `ChatReply` 增加 `modify_patch` 字段（destination/dates/budget/preferences 的 patch） | ⬜ | schemas/chat.py |
| T1.2.2 | `conversation.py` 处理 `modify_plan` intent：解析增量修改 → 合并到既有 plan_request → 重置 ready | ⬜ | conversation.py |
| T1.2.3 | 前端 chatStore 检测 modify 后用 patch 重置 form 并可重新 beginPlanning | ⬜ | frontend |

**验收清单**：
- [ ] "预算加到8千" 在已有 session 内解析为 budget patch
- [ ] "再加一天" 解析为 end_date 推移（注意天数边界）

### P1.3 M9 对话前端

| 任务 ID | 内容 | 状态 | 产出 |
|---------|------|------|------|
| T1.3.1 | `frontend/src/types/chat.ts`：ChatMessage/ChatReply/Slots | ⬜ | types/chat.ts |
| T1.3.2 | `frontend/src/services/chat.ts`：`postChat()` 封装 /api/chat | ⬜ | services/chat.ts |
| T1.3.3 | `frontend/src/stores/chatStore.ts`：messages/slots/session_id/status | ⬜ | stores/chatStore.ts |
| T1.3.4 | `frontend/src/components/Chat/ChatWindow.tsx`：用户/assistant 气泡 | ⬜ | components/Chat/ |
| T1.3.5 | `frontend/src/components/Chat/ChatInput.tsx`：输入框+发送 | ⬜ | components/Chat/ |
| T1.3.6 | `frontend/src/components/Chat/SlotPanel.tsx`：侧边已收集槽位可视化 + 可点击编辑 | ⬜ | components/Chat/ |
| T1.3.7 | `frontend/src/pages/Chat.tsx`：主页面，ready=true → startPlan → /loading?plan_id | ⬜ | pages/Chat.tsx |
| T1.3.8 | `App.tsx` 路由：`/` → Chat，`/form` 保留旧表单（兼容+E2E） | ⬜ | App.tsx |
| T1.3.9 | sessionStorage 持久化 session_id；首次进入 assistant 主动发首条 | ⬜ | Chat.tsx |

**验收清单**：
- [ ] 全程自然语言完成需求表达，无需触碰表单
- [ ] assistant 追问温暖清晰（复用情侣文案风格）
- [ ] 槽满无缝切 Loading→PlanResult（SSE 复用）
- [ ] 刷新页面对话不丢（sessionStorage）
- [ ] `/form` + 既有 Playwright E2E 不破坏
- [ ] tsc 检查 + Vite 构建 + 移动端响应式通过

**P1 阶段出口**：curl /api/chat 走通 + Chat UI 可用 → 进入 P2。

---

## P2 内容质量（替代 M10 pgvector）（前置：无，可与 P1 部分并行）

**目标**：不上向量库，靠评分算法重写 + 人工 curated + 反馈循环提升推荐参考性。

### P2.1 couple_score 算法重写

| 任务 ID | 内容 | 状态 | 产出 |
|---------|------|------|------|
| T2.1.1 | `poi_search_tool.py` `_couple_score` 改为：rating 权重 0.5 + 类型匹配偏好 0.3 + 室内/户外季节适配 0.2 | ⬜ | poi_search_tool.py |
| T2.1.2 | 同步 `food_search_tool.py` 评分逻辑去重/统一 | ⬜ | food_search_tool.py |
| T2.1.3 | 单测覆盖新算法各权重分支 | ⬜ | test_tools.py |

### P2.2 人工 curated 覆盖

| 任务 ID | 内容 | 状态 | 产出 |
|---------|------|------|------|
| T2.2.1 | `backend/data/curated_pois.json`：大理/三亚/杭州/成都/厦门 各 5–10 精选，手工描述 | ⬜ | data/curated_pois.json |
| T2.2.2 | `search_poi` 先查 curated（city+preferences 过滤），不足补 Amap | ⬜ | search_poi.py |
| T2.2.3 | curated 项 source 字段标记，供 UI 展示「精选」徽章 | ⬜ | search_poi.py + 前端 badge |

### P2.3 用户反馈闭环（与 P3 storage 协同）

| 任务 ID | 内容 | 状态 | 产出 |
|---------|------|------|------|
| T2.3.1 | `PlanStore` 加 `feedback(plan_id, activity_name, thumbs)` 表 | ⬜ | storage.py |
| T2.3.2 | 新增 `POST /api/plan/{id}/feedback` 端点 | ⬜ | main.py |
| T2.3.3 | 离线脚本 `scripts/recompute_scores.py` 按反馈重算 couple_score | ⬜ | scripts/ |
| T2.3.4 | 前端行程活动卡片加 👍/👎 按钮 | ⬜ | TimelineCard.tsx |

**验收清单**：
- [ ] 搜索结果真实 rating 主导排序，非类型硬编码
- [ ] curated 项优先于 Amap 同名项
- [ ] 反馈写入 PostgreSQL，recompute 脚本可重算
- [ ] 无 pgvector 依赖（复用 P0.1 的 postgres 服务，不额外加 db）

---

## P3 工程化（前置：P0 全完成；可与 P2 并行）

**目标**：达到生产门槛。

### P3.1 鉴权 + 限流

| 任务 ID | 内容 | 状态 | 产出 |
|---------|------|------|------|
| T3.1.1 | `config/settings.py` 加 `api_keys: list` 从 env 读白名单 | ⬜ | settings.py |
| T3.1.2 | FastAPI 依赖 `verify_api_key` 校验 `X-API-Key` | ⬜ | main.py / deps.py |
| T3.1.3 | `slowapi` 中间件，`/api/plan` 10次/分/IP，`/api/chat` 30次/分/IP | ⬜ | main.py |
| T3.1.4 | 前端打包注入 API key（Vite env） | ⬜ | frontend |

### P3.2 可观测性

| 任务 ID | 内容 | 状态 | 产出 |
|---------|------|------|------|
| T3.2.1 | `structlog` 替换裸 logging，结构化 JSON 日志 | ⬜ | 全后端 |
| T3.2.2 | `prometheus-fastapi-instrumentator` 暴露 `/metrics` | ⬜ | main.py |
| T3.2.3 | OpenTelemetry tracing：至少 instrument LLM + Amap/QWeather 调用 | ⬜ | services/ |
| T3.2.4 | SSE `complete` payload 加 `degraded` 标志（复用 issues 文档 P10 思路） | ⬜ | main.py |

### P3.3 配置规范化

| 任务 ID | 内容 | 状态 | 产出 |
|---------|------|------|------|
| T3.3.1 | `config/settings.py` 迁 `pydantic-settings.BaseSettings` | ⬜ | settings.py |
| T3.3.2 | 支持 `.env.dev`/`.env.prod` 分层；CORS origins 从 env 读 | ⬜ | settings.py + main.py |
| T3.3.3 | `pyproject.toml` 与 `requirements.txt` 合并为单一来源 | ⬜ | pyproject.toml |

### P3.4 外部 API 韧性

| 任务 ID | 内容 | 状态 | 产出 |
|---------|------|------|------|
| T3.4.1 | `services/amap.py` 加指数退避重试 3 次（`tenacity`） | ⬜ | amap.py |
| T3.4.2 | QWeather 调用同上 | ⬜ | qweather_auth.py/天气工具 |
| T3.4.3 | 熔断器：连续失败 5 次短路 30s（`purgatory` 或自实现） | ⬜ | services/ |

**验收清单**：
- [ ] 无 key 请求被 401 拒绝
- [ ] 超 10 次/分 触发 429
- [ ] `/metrics` 可采集
- [ ] LLM/Amap 调用 span 可见（Jaeger / console exporter）
- [ ] Amap 连续失败 5 次后 30s 内直接降级不再发请求

---

## 全局约束

- **回归红线**：每个任务 PR 必须附 `pytest -q` 输出与 `npm run build` 输出截屏/日志。
- **分支策略**：建议每阶段一个 feature 分支（`feat/p0-foundation`、`feat/p1-conversational`…），阶段内任务可在该分支累计。
- **回滚**：PostgreSQL volume、Redis 数据均为可丢弃态，回滚仅需 revert 代码 + 清 volume；无破坏性 schema 迁移。
- **依赖新增清单**（P0–P3 累计）：`psycopg[binary]>=3.1`、`psycopg_pool`、`redis`、`slowapi`、`structlog`、`prometheus-fastapi-instrumentator`、`opentelemetry-sdk`+`opentelemetry-instrumentation-fastapi`、`tenacity`。P2 无新增依赖。

---

## 执行次序建议

```
P0.1 ──┐
P0.2 ──┼─→ P0.3 ──→ P1.1 ──→ P1.3
                   P1.2 ─────┘
P2.* ──────────────────────（可与 P1 并行，独立后端增量）
P3.* ──────────────────────（P0 完成后任意时点插入）
```

P0.1/P0.2 互不依赖可并行；P0.3 必须等 P0.1（plan_id）。P1 严格依赖 P0.3。P2/P3 不阻塞 P1，按人力灵活排。
