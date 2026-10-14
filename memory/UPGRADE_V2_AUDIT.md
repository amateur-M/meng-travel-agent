## V2 优化方案审查与重排（企业级视角）

> 本文档基于对前后端实际代码的逐文件审查，对 `UPGRADE_CONVERSATIONAL.md`（M8/M9/M10）方案进行评估与修订。
> 不是对小修小补，而是从企业级生产视角重新排优先级：先补地基，再做对话，最后内容质量。
> 文档中的文件/行号引用均基于审查时点的真实代码。

---

## 一、现状诊断：被文档掩盖的技术债

文档说"183 测试全绿、M7 交付"，但代码里有几处**地基级隐患**，在做任何新功能前必须正视。

### 1.1 同步 LLM 阻塞 async 事件循环

**位置**：`backend/services/llm.py:145`

```python
response = llm.invoke(messages)   # 同步阻塞调用
```

而 `backend/main.py:149` 用 `graph.astream()`（async）。所有节点函数都是 `def` 而非 `async def`，LangGraph 会丢进线程池跑——意味着每个 LLM 调用占住一个线程 1–3 秒。单进程下并发几个请求就会耗尽线程池。

**企业级要求**：`async def` 节点 + `llm.ainvoke()`，否则上量即崩。

### 1.2 持久化承诺未兑现

**位置**：`backend/main.py`

ARCHITECTURE.md:145–147 文档列了 4 个 REST 端点：`GET /api/plan/{plan_id}`、`GET /api/plan/history`、`DELETE /api/plan/{plan_id}`。**实际代码只有 `POST /api/plan` + `GET /health`**。

行程生成完就丢，刷新页面 plan 全没。前端靠 Zustand 内存 store 撑着（`frontend/src/stores/tripStore.ts`），一旦刷新 `/result` 页直接白屏。这是"交付"了但实际不可用。

### 1.3 SSE 重试 = 重新规划

**位置**：`frontend/src/services/sse.ts:85–112`

```typescript
while (true) {
  await consumeOnce(url, handlers, ...)  // 重新 POST /api/plan
  if (!completed) { attempt++; retry }
}
```

断线重连会**重新发起 POST /api/plan，重跑整条 LangGraph 管线**。不是断点续传，是重新规划——浪费算力、结果可能不同、用户已看到的 partial 会被覆盖。

**根因**：后端没有 plan_id 持久化，无法"重连到同一个流"。

### 1.4 外部 API 无重试/熔断

**位置**：`backend/services/amap.py:55`、qweather 调用处

只有 `timeout=15`，一次失败就进 warnings 软失败。无指数退避重试、无熔断器、无并发上限。多用户并发时 Amap/QWeather 限流会级联失败。

### 1.5 无鉴权 / 无限流 / CORS 硬编码

**位置**：`backend/main.py:26`

```python
allow_origins=["http://localhost:5173"]  # 硬编码
```

无 API key、无 rate limit。任何人可无限调用 `/api/plan` 触发昂贵 LLM 管线——**直接的成本安全漏洞**。

### 1.6 add_couple_touch 性能热点未验证

文档说"批量 LLM 调用为每个活动生成情侣寄语"。3 天 × 6 活动 = 18 次 LLM 调用？还是一次调用生成全部？如果是前者，这是管线最慢的节点，且没看到并发批处理。需要在 P0 阶段验证并改造。

---

## 二、对 UPGRADE_CONVERSATIONAL.md 的逐项评估

### M8 对话后端——方向对，细节有坑

| 设计点 | 评估 | 备注 |
|--------|------|------|
| 双端点（/api/chat JSON + /api/plan SSE） | ✅ 正确 | 对话轻、规划重，拆开合理 |
| 纯函数 handle_chat（方案 A） | ✅ MVP 正确 | 不该上 LangGraph |
| 内存 dict session store + TTL | ❌ **容器化必丢** | uvicorn 多 worker 各持一份内存，请求落到不同 worker 会话断裂；Compose 部署就出问题 |
| 槽位靠 LLM structured output 一次性产出 | ⚠️ 可靠性存疑 | 日期解析（"下周末"→具体日期）需确定性后处理校验层兜底 |
| modify_plan 预留到 V2.1 | ⚠️ 值得提前 | 体验收益可能比 M9 对话前端更高 |

### M9 对话前端——合理但依赖 M8 稳定

SlotPanel 可编辑、sessionStorage 持久化 session_id 都对。但"槽满后无缝切换到既有 Loading→PlanResult"的前提是规划结果可持久化——而 1.2 节说了，目前刷新就丢。

### M10 pgvector——投入产出比最低，建议大改

这是最想推翻的部分，理由如下：

1. **播种质量不可控**：靠 LLM 生成"情侣向 80 字描述" + couple_score，是无监督的一次性生成，无真实用户反馈校准。垃圾进垃圾出，向量化只是让"检索更准"，但库里本身质量存疑。
2. **ivfflat 索引过度设计**：精选几百到几千条 POI，暴力余弦搜索毫秒级就够，`lists=100` 的 ivfflat 需要数据量上万才有效，反而降低小数据集召回率。
3. **Embedding 单点依赖 OpenAI 1536 维**：项目主打多 provider（DeepSeek/Qwen/Kimi），但 embedding 只走 OpenAI，且无降级。OpenAI key 没配向量库就废了。
4. **维护成本高**：每加一个城市要重新播种，couple_score 会过时无更新机制。
5. **真正痛点 mismatch**：当前 POI 的问题不是"缺语义描述"，而是 `couple_score` 是规则硬算的（`backend/tools/poi_search_tool.py:77` 的 `_CATEGORY_BASE_SCORE` 字典），不是真实评分。**改 couple_score 算法 + 加人工 curated 覆盖，比上向量库收益更快**。

**结论**：M10 应从"pgvector 全套"降级为"人工 curated JSON + 评分规则优化"，向量库延后到有真实用户反馈数据后再做。

---

## 三、优先级重排

文档建议顺序：M8 → M10 → M9。建议**完全重排**，先补地基再谈对话：

```
P0 地基修复（不做就无法稳定支撑任何新功能）
  ├─ 行程持久化（兑现文档承诺的 REST 端点）
  ├─ LLM 异步化（async def + ainvoke）
  └─ SSE 断线重连改为重连同一 plan 流（不重跑）

P1 对话式（M8/M9，方向保留）
  ├─ M8 后端：会话存储改 Redis（非内存 dict）
  └─ M9 前端：Chat UI

P2 内容质量（替代 M10 pgvector）
  └─ POI 评分优化 + 人工 curated + 用户反馈循环

P3 工程化（生产门槛）
  ├─ 鉴权 + 限流
  ├─ 可观测性（结构化日志 + metrics + tracing）
  └─ 配置规范化（Pydantic Settings + 环境分层）
```

**理由**：P0 是"已交付功能实际不可用"的硬伤，不补就做对话式等于在沙地上盖楼。M8/M9 依赖 P0 的持久化（对话生成的 plan 要能存、能刷新恢复）。

---

## 四、各模块企业级设计细节

### P0.1 行程持久化（最关键）

**决策**：采用 **PostgreSQL** 作为统一持久化层，承载行程存储、用户反馈，并为后续对话会话（M8 Redis 之外的跨设备续聊）、向量库（未来 M10 若重启）等业务预留同库扩展空间。一步到位避免 SQLite→Postgres 迁移返工。

```
docker-compose.yml 新增 db 服务（postgres:16-alpine）
backend/services/storage.py
  - PlanStore: save(plan_id, request, response, status, created_at)
  - get(plan_id) / list(limit, offset) / delete(plan_id)
  - 依赖 psycopg （异步用 psycopg-pool / asyncpg）
  - 自动建表（DDL 幂等）+ 连接池
```

`POST /api/plan` 改造：
1. 入口先生成 `plan_id`，写一条 `status=processing` 记录
2. 管线跑完在 `output_format` 后写回 `status=completed` + 完整 response
3. 新增 `GET /api/plan/{plan_id}` 读库返回
4. SSE 流的 `complete` 事件带 `plan_id`，前端刷新 `/result?plan_id=xxx` 可恢复

**新增 REST 端点**（兑现 ARCHITECTURE.md 承诺）：
- `GET /api/plan/{plan_id}` — 查询已完成行程详情
- `GET /api/plan/history` — 历史行程列表（分页）
- `DELETE /api/plan/{plan_id}` — 删除历史行程

**取舍**：PostgreSQL 功能完备、支持 JSONB（存行程 response 半结构化）、并发成熟；后续对话会话表、向量库（若启用 pgvector 扩展）、用户反馈表共用同一实例，省去多数据源运维。代价是多一个容器，但 docker-compose 已有编排基础。

### P0.2 LLM 异步化

**改造范围**：
- 所有节点函数改 `async def`
- `backend/services/llm.py` 拆出 `async def acall_llm` 用 `llm.ainvoke()`
- `add_couple_touch` 如果是逐活动调用，改为 `asyncio.gather` 并发批处理（限并发 5，避免 API 限流）

**收益**：LangGraph 的 `astream` 对 async 节点直接 `await`，不再过线程池，事件循环不被阻塞，并发吞吐提升明显。

### P0.3 SSE 断线重连不重跑

后端 `/api/plan` 改为两段式生命周期：

| 端点 | 作用 |
|------|------|
| `POST /api/plan` | 创建 plan_id + 投递后台任务 + 返回 `{plan_id, stream_url}` |
| `GET /api/plan/{plan_id}/stream` | SSE 端点，从内存实时事件队列消费（或从 PostgreSQL 重放最终结果） |

前端 `postEventStream` 重试时改连 `GET .../stream`，不重新 POST。这与 UPGRADE 文档原设想一致，但需要后端先把 plan 生命周期拆开。

### P1.1 M8 对话后端（修订版）

保留双端点设计，**两处关键修改**：

**修改 1：会话存储用 Redis**（非内存 dict）
- `docker-compose.yml` 加 `redis` 服务
- `backend/services/session_store.py` 用 `redis.asyncio`
- key 为 `chat:{session_id}`，TTL 30 分钟
- 槽位合并逻辑在 Redis 里原子操作（`HGETALL` + `HSET`）
- 好处：跨 worker / 跨容器 / 跨刷新都能续聊

**修改 2：槽位提取加确定性后处理**
- LLM 先出 raw slots
- `postprocess_slots()` 用 `datetime` + 正则做日期校验（"下周末"→`date.today()` 推算）
- budget 单位归一（"5千"→5000、"两人5000"→5000）
- 校验失败在 reply 里追加"确认一下：你说的是 X 月 X 日对吗？"

**意图分类（保留原文档 taxonomy）**：

| intent | 含义 | 触发规划？ |
|--------|------|-----------|
| `greeting` | 打招呼/闲聊 | 否 |
| `question` | 通用旅行知识提问 | 否 |
| `planning_intent` | 表达出行意愿，提取槽位 | 否（除非槽满） |
| `planning_ready` | 槽位已齐 | 是 |
| `modify_plan` | 已有行程后要求调整 | 是（建议提前到 P1） |

**槽位定义（保留，补充后处理）**：

| 槽位 | 必填 | 后处理策略 |
|------|------|-----------|
| `destination` | 是 | 城市名实体识别 + adcode 校验（`backend/services/amap.py:CITY_ADCODE`） |
| `start_date`/`end_date` | 是 | 相对日期解析 + 绝对日期校验 |
| `budget` | 是 | 数字 + 单位归一 |
| `origin` | 否 | 默认"北京" |
| `preferences` | 否 | 标签映射 |
| `pace` | 否 | 默认"轻松" |

### P1.2 M9 对话前端

基本照原文档，但 `ready=true` 后的流程改为：
1. POST /api/plan 拿 plan_id
2. 跳 `/loading?plan_id=xxx`
3. 连 GET stream
4. 完成跳 `/result?plan_id=xxx`

这样刷新任何页面都能用 plan_id 恢复。

**产出文件清单（保留原文档）**：
- `frontend/src/pages/Chat.tsx`
- `frontend/src/components/Chat/ChatWindow.tsx`
- `frontend/src/components/Chat/ChatInput.tsx`
- `frontend/src/components/Chat/SlotPanel.tsx`
- `frontend/src/services/chat.ts`
- `frontend/src/stores/chatStore.ts`
- `frontend/src/types/chat.ts`
- 路由调整：`App.tsx` 默认 `/` → Chat，`/form` 保留旧表单

### P2 内容质量（替代 M10 pgvector）

不上 pgvector，改做三件轻量事：

**1. couple_score 算法重写**

位置：`backend/tools/poi_search_tool.py:77`（当前 `_couple_score`）

- 当前：`_CATEGORY_BASE_SCORE` 字典 + rating 微调（类型硬编码）
- 改为：rating 权重 0.5 + 类型匹配偏好 0.3 + 室内/户外季节适配 0.2
- 真实评分主导，而非类型硬编码

**2. 人工 curated JSON 覆盖**

- 新建 `backend/data/curated_pois.json`：每城市 5–10 个情侣精选（手工维护，带真实描述）
- `search_poi` 先查 curated（按 city + preferences 过滤），不足再补 Amap
- 比向量化 100 条 LLM 生成的描述更可控

**3. 用户反馈闭环（与 P3 一起做）**

- 行程完成后让用户给某活动点赞/踩
- 反馈写回 PostgreSQL，定期离线重算 couple_score
- 这是真正让推荐变准的方式，比向量化强

### P3 工程化

| 项目 | 方案 |
|------|------|
| 鉴权 | `/api/chat` + `/api/plan` 加 `X-API-Key` header 校验（env 白名单），前端打包注入 |
| 限流 | `slowapi` 中间件，`/api/plan` 限 10 次/分钟/IP（LLM 成本保护） |
| 可观测性 | `structlog` 结构化日志 + `prometheus-fastapi-instrumentator` metrics + OpenTelemetry tracing（至少 trace LLM + 外部 API 调用） |
| 配置 | `backend/config/settings.py` 改 `pydantic-settings.BaseSettings`，支持 `.env.dev`/`.env.prod` 分层，CORS 从 env 读 |
| 外部 API 韧性 | Amap/QWeather 加指数退避重试（3 次）+ 熔断器（连续失败 5 次短路 30s） |

---

## 五、与 UPGRADE_CONVERSATIONAL.md 的差异对比

| 维度 | UPGRADE 文档 | 本方案 |
|------|-------------|--------|
| 优先级 | M8→M10→M9 | P0 地基→P1 对话→P2 内容→P3 工程化 |
| 持久化 | 未提（M8 靠内存） | P0 先补 PostgreSQL 行程持久化 |
| 会话存储 | 内存 dict + TTL | Redis |
| LLM 调用 | 未提同步问题 | async 化 + 并发批处理 |
| SSE 重连 | 未提重跑问题 | plan_id + GET stream 重连 |
| 向量库 | M10 pgvector 全套 | 砍掉，改评分优化 + curated + 反馈循环 |
| modify_plan | V2.1 预留 | 提到 P1 后段（收益高） |
| 鉴权限流 | 未提 | P3 生产门槛 |
| 可观测性 | 未提 | P3 生产门槛 |

**核心立场**：文档把"对话式"当首要目标，但当前地基（持久化、异步、重连）没补，对话式建上去会继承所有不可用问题。pgvector 是过度工程，真实痛点是 couple_score 算法而非缺向量。

---

## 六、建议实施顺序与验收门槛

```
P0 地基修复
  ├─ P0.1 行程持久化（PostgreSQL + REST 端点补齐）
  ├─ P0.2 LLM 异步化（async def + ainvoke + 并发批处理）
  └─ P0.3 SSE 断线重连不重跑（plan_id + GET stream）
      验收：刷新 /result?plan_id=xxx 可恢复；断线重连不重跑管线；既有 183 测试零回归

P1 对话式
  ├─ P1.1 M8 后端（Redis 会话 + 槽位后处理）
  ├─ modify_plan 增量调整（提前从 V2.1）
  └─ P1.2 M9 前端（Chat UI + plan_id 路由恢复）
      验收：curl /api/chat 可走通意图识别；刷新页面对话不丢；既有 /form + E2E 不破坏

P2 内容质量
  ├─ couple_score 算法重写
  ├─ curated_pois.json 人工精选覆盖
  └─ 用户反馈点踩写入 PostgreSQL
      验收：搜索结果真实评分主导；curated 覆盖优先；无 pgvector 依赖

P3 工程化
  ├─ 鉴权 + 限流
  ├─ 可观测性（日志 + metrics + tracing）
  ├─ 配置规范化
  └─ 外部 API 韧性（重试 + 熔断）
      验收：无 key 不可调用；LLM 调用可追踪；Amap 连续失败自动熔断
```

每个阶段结束保持「后端测试全绿 + 前端构建通过 + 既有 E2E 不回归」的硬门槛。
