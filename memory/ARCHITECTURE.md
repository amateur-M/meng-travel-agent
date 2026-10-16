## 1. 系统总体架构

```
┌──────────────┐     HTTP/REST + SSE       ┌──────────────────────────┐
│              │ ◄────────────────────── ► │                          │
│   Frontend   │                           │        Backend           │
│   React 18   │                           │    FastAPI + LangGraph   │
│   TypeScript │                           │                          │
│              │                           │  ┌────────────────────┐  │
└──────────────┘                           │  │   LangGraph Agent  │  │
                                           │  │   (Graph + Nodes)  │  │
                                           │  └────────┬───────────┘  │
                                           │           │              │
                                           │  ┌────────▼───────────┐  │
                                           │  │   External APIs    │  │
                                           │  │  - Weather Service │  │
                                           │  │  - Map/POI Service │  │
                                           │  │  - OpenAI GPT-4o   │  │
                                           │  └────────────────────┘  │
                                           └──────────────────────────┘
```

**前端**：单页应用，负责用户交互、表单输入、行程渲染、SSE 流式消费。
**后端**：API 网关 + Agent 引擎。FastAPI 处理 HTTP 请求，LangGraph 编排行程规划的多步推理链路。
**外部服务**：天气 API（和风天气/OpenWeatherMap）、地图 API（高德/Google Maps）、LLM（OpenAI GPT-4o）。

---

## 2. LangGraph Agent 设计

### 2.1 State 定义（TripPlanState）

```python
from typing import TypedDict, Annotated, List
from langgraph.graph.message import add_messages
from app.models.trip import TripPlan, DayPlan, Activity, BudgetSummary

class TripPlanState(TypedDict):
    # ── 用户输入 ──
    origin: str                    # 出发地
    destination: str               # 目的地
    start_date: str                # 开始日期 (YYYY-MM-DD)
    end_date: str                  # 结束日期 (YYYY-MM-DD)
    budget: float                  # 总预算（元）
    preferences: List[str]         # 偏好标签：["浪漫", "美食", "户外", "文化"]
    pace: str                      # 节奏偏好："轻松" | "适中" | "充实"

    # ── 外部数据（中间结果） ──
    weather_data: dict             # { date: { condition, temp_high, temp_low, ... } }
    poi_attractions: List[dict]    # 景点列表
    poi_restaurants: List[dict]    # 餐厅列表
    poi_indoor: List[dict]         # 室内备选（雨天使用）

    # ── Agent 产出 ──
    itinerary: TripPlan            # 最终行程
    budget_summary: BudgetSummary  # 预算摘要
    messages: Annotated[list, add_messages]  # LLM 对话历史

    # ── 流程控制 ──
    current_step: str              # 当前步骤标识
    errors: List[str]              # 异常收集
```

### 2.2 Node 列表

| Node | 职责 | 输入 | 输出 |
|------|------|------|------|
| `parse_input` | 解析并校验用户输入，补全默认值 | 原始请求 | 规范化后的 state |
| `fetch_weather` | 调用天气 API，获取行程日期范围内的天气 | destination, dates | weather_data |
| `search_poi` | 调用地图 POI API，搜索景点（含室内备选标记） | destination, preferences | poi_list |
| `search_food` | 调用地图 API，搜索餐厅 | destination, preferences | food_list |
| `plan_itinerary` | 调用 LLM 生成初步行程骨架 | weather + pois + 偏好 | draft_itinerary |
| `rhythm_control` | M5 节奏控制：每档≤2活动 + 留白注入（确定性规则，无 LLM） | draft_itinerary | draft_itinerary (normalised), rhythm_adjustments |
| `budget_check` | 核算每项花费，超预算时确定性降级（M4 后为原地降级，不再重试） | draft_itinerary + budget | draft_itinerary (adjusted), budget_breakdown |
| `adapt_weather` | 根据天气条件调整行程（雨天/高温切换） | draft_itinerary + weather_data | draft_itinerary (weather-adjusted), weather_swaps |
| `add_couple_touch` | 批量 LLM 调用为每个活动生成情侣寄语（P7 优化，M5 增强时段差异化） | draft_itinerary | draft_itinerary (with couple_note), couple_notes |
| `output_format` | 最终归一化、补 trip_date/天气高低温/daily_cost、格式化为 TripPlanResponse | draft_itinerary + budget + notes + rhythm | final_itinerary |

> 注：节点名以实际代码为准（`parse_input`/`search_poi`/`search_food`/`plan_itinerary`/`budget_check`/`adapt_weather`/`add_couple_touch`/`output_format`），与上文规划稿的 `gather_input`/`search_pois`/`generate_itinerary`/`apply_budget`/`weather_adapt`/`add_couple_messages`/`finalize_plan` 略有差异。

### 2.3 Edge / 流程编排

```
                  ┌──────────────┐
                  │  START       │
                  └──────┬───────┘
                         │
                  ┌──────▼───────┐
                  │ parse_input  │
                  └──────┬───────┘
                         │
           ┌─────────────┼─────────────┐
           │             │             │
    ┌──────▼───────┐ ┌───▼────────┐ ┌──▼─────────┐
    │ fetch_weather│ │ search_poi │ │search_food │   ← 三路并行（fan-out）
    └──────┬───────┘ └───┬────────┘ └──┬─────────┘
           │             │             │
           └─────────────┼─────────────┘
                         │
                  ┌──────▼───────────┐
                  │ plan_itinerary   │
                  └──────┬───────────┘
                         │
                  ┌──────▼───────────┐
                  │ rhythm_control   │   ← M5: 每档≤2活动 + 留白注入
                  └──────┬───────────┘
                         │
                  ┌──────▼───────┐
                  │ budget_check │   ← 原地确定性降级（M4，不再重试）
                  └──────┬───────┘
                         │
                  ┌──────▼────────┐
                  │ adapt_weather │
                  └──────┬────────┘
                         │
                  ┌──────▼─────────────┐
                  │ add_couple_touch   │   ← 批量 LLM 调用（P7）+ 时段差异化（M5）
                  └──────┬─────────────┘
                         │
                  ┌──────▼───────┐
                  │output_format │
                  └──────┬───────┘
                         │
                  ┌──────▼───────┐
                  │     END      │
                  └──────────────┘
```

**条件分支说明**：
- `budget_check`（M4 后）：累计花费超预算时执行**原地确定性降级**（替换高价 POI/餐厅），然后**直接进入** `adapt_weather`。早期的条件重试回路已在 P6 删除（`budget_check → plan_itinerary` 分支不可达死代码）。
- `adapt_weather` 内部：若全部晴天，无操作；若有雨天/高温，触发方案切换（rule-based 兜底，LLM 路径可选增强）。
- 三路 fan-out 的 `current_phase` 用 `_latest_str` reducer、`warnings` 用 `operator.add`，避免并行写入冲突。

### 2.4 对话记忆分层（V3）

Agent 从"单轮提取器"变成"能持续对话"的关键。四层各司其职，**L1–L3 全部用结构化
存储 + SQL 召回实现，不需要 embedding** —— "要有长期记忆"与"V2 拒绝 pgvector"
并不冲突，二者曾被混为一谈。

| 层 | 名称 | 内容 | 存放 | 注入方式 |
|----|------|------|------|----------|
| **L0** | 工作记忆 | 最近 10 轮（20 条）原文，**单条 ≤2000 字符、整块 ≤8000 字符** | `chat_messages` | 真实多轮 Human/AI 消息 |
| **L1** | 会话内长期记忆 | 滑出窗口部分的滚动摘要 | `chat_sessions.summary` + `summary_message_count` 游标 | system prompt 段落 |
| **L2** | 跨会话画像 | 出发地/节奏/偏好/预算区间/忌口 | `user_profiles`（key = 浏览器 `client_id`） | system prompt 段落 |
| **L3** | 情节记忆 | 历史行程、去过的目的地、活动级 👍/👎 | `plans` + `plan_feedback` | system prompt 段落 |
| **L4** | 语义检索 | 模糊语义召回 | — | **延后**；需要时先用 `tsvector`/`pg_trgm`，仍不必上 pgvector |

**prompt 组装顺序固定**（由测试钉住）：角色与规则 → L2 画像 → L3 行程 → L1 摘要 →
L0 真实消息。最持久的事实在前，最易变的在后。

**L1 的增量语义**：`summary_message_count` 记录摘要已覆盖多少条消息，因此每次只需
压缩"新滑出的那一段"，并与已有摘要合并（送给模型时带"已有摘要"，不是覆盖）。
溢出不足 `SUMMARY_MIN_NEW_MESSAGES`（4 条）不触发，避免每轮多花一次 LLM 调用。

**L2 的合并规则**：只增不删。集合字段取并集；标量被替换时旧值进入 `conflicts`，
prompt 会渲染成"出发地：上海（此前提到过：北京）"，而不是假装用户没说过。

**两段式 LLM 调用**（成本控制）：

```
Call 1（总是）：意图 + 槽位 + modify_patch + reply  ← 结构化 JSON，带 L0 history
Call 2（仅 question / greeting）：自由文本真回答（acall_llm_text）
规划类（planning_intent / planning_ready / modify_plan）：
    直接用 Call 1 返回的 reply 文案；模型没给文案时才用确定性模板兜底。
    **不额外调用**，因为"还差哪些信息""改成了什么"是可确定表达的。
```

**L0 预算**：窗口 20 条只是上限，实际进 prompt 的内容还受两道字符上限约束 ——
单条 2000 字符、整块 8000 字符；超预算时**从最旧的一条开始丢**（L1 摘要已承载
旧内容，而丢掉紧跟当前消息的那一轮会恰好破坏"那改成三天呢"这类追问）。
由 `tests/test_llm_history.py` 钉住。

**数据模型（PostgreSQL，与 `plans` 同库）**：

```sql
chat_sessions(session_id PK, title, summary, summary_message_count,
              slots JSONB, plan_request JSONB, last_plan_id, client_id,
              created_at, updated_at)
chat_messages(id PK, session_id FK→chat_sessions ON DELETE CASCADE,
              message_id UNIQUE, role, content, created_at)
user_profiles(client_id PK, user_id, profile JSONB, updated_at)
```

`message_id` 唯一约束是幂等的支点：客户端重试同一个 `message_id` 时
`ON CONFLICT DO NOTHING`，不会把用户那句话写两遍。

**存储层为何是"同步驱动 + 线程卸载"**：`services/conversation_store.py` 与
`services/storage.py`（`PlanStore`）都用同步 `psycopg` 连接池，**所有** DB 调用
经 `asyncio.to_thread` 卸载。psycopg 的**异步**模式在 Windows 默认的
`ProactorEventLoop` 上直接报 `InterfaceError`，而 Windows 是主要开发平台。
P0.2 的要求是"不阻塞事件循环"，线程卸载同样满足且跨平台一致。
（由 `tests/test_event_loop.py` 以事件循环延迟度量守住：任一存储调用回到循环上，
测试立即失败。）

---

## 3. 前后端通信接口

### 3.1 REST API

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 + **存储状态**（`storage.postgres` / `storage.chat`，含失败原因） |
| `POST` | `/api/plan` | 提交行程规划请求，返回 `plan_id`（可带 `session_id` 关联对话） |
| `GET` | `/api/plan/{plan_id}` | 查询已完成的行程详情 |
| `GET` | `/api/plan/{plan_id}/stream` | SSE 端点，流式推送规划进度 |
| `GET` | `/api/plan/history` | 历史行程列表（分页） |
| `DELETE` | `/api/plan/{plan_id}` | 删除历史行程 |
| `POST` | `/api/plan/{plan_id}/feedback` | 活动级 👍/👎 反馈（L3 情节记忆的数据源） |
| `POST` | `/api/chat` | 对话：意图 + 槽位 + 回复（V3：带记忆、落库、幂等） |
| `GET` | `/api/chat/sessions` | 对话列表（分页，最近活跃倒序，驱动侧边栏） |
| `GET` | `/api/chat/sessions/{id}` | 会话详情（slots / summary / plan_request / last_plan_id） |
| `GET` | `/api/chat/sessions/{id}/messages` | 完整对话记录（分页，含 `message_id` 供幂等重试） |
| `PATCH` | `/api/chat/sessions/{id}` | 重命名会话 |
| `DELETE` | `/api/chat/sessions/{id}` | 删除会话（消息级联删除） |
| `GET` | `/api/profile` | L2 跨会话画像读取 |
| `PATCH` | `/api/profile` | L2 画像手工纠正（沿用同一套合并规则，不抹掉已学到的） |
| `GET` | `/api/chat/recall` | L3 情节记忆预览（历史行程 + 活动反馈） |

**POST /api/plan 请求体**：

```json
{
  "origin": "北京",
  "destination": "大理",
  "start_date": "2026-09-01",
  "end_date": "2026-09-03",
  "budget": 5000,
  "preferences": ["浪漫", "美食", "自然"],
  "pace": "轻松",
  "session_id": "对话会话 ID（可选，传入则行程会关联回该对话）"
}
```

**响应**：

```json
{
  "plan_id": "uuid",
  "status": "processing",
  "stream_url": "/api/plan/uuid/stream"
}
```

**POST /api/chat 请求体**：

```json
{
  "message": "预算加到8千",
  "session_id": "可选，首次不传则新建",
  "client_id": "浏览器侧稳定 id（localStorage），用于会话隔离与 L2 画像",
  "message_id": "客户端生成的轮次 id；同 id 重试不会重复写入"
}
```

### 3.2 SSE 协议

端点：`POST /api/plan`（M6 实际实现：POST 流式返回，非 GET 轮询）

事件类型（M6 实际实现，`stream_mode="updates"` 逐节点发射）：

| event | data | 说明 |
|-------|------|------|
| `step` | `{ "phase": "fetch_weather", "message": "正在查询大理天气..." }` | 当前阶段（每个节点完成时发射） |
| `partial` | `{ "day_index": 0, "period": "all", "activities": [...], "weather": "晴" }` | 逐日行程数据（plan_itinerary/rhythm_control 后发射） |
| `budget_alert` | `{ "current": 5200, "limit": 5000, "warning_level": "over", "spending_ratio": 1.04, "downgrade_applied": true, "suggestions": [...], "downgrade_notes": [...] }` | 预算预警（budget_check 后） |
| `weather_swap` | `{ "day_index": 0, "original": "洱海骑行", "replacement": "室内咖啡馆", "reason": "雨天切换", "adjustment_type": "swap" }` | 天气方案切换（adapt_weather 后，逐项发射） |
| `message` | `{ "day": 1, "activity": "洱海骑行", "text": "和你一起..." }` | 情侣寄语生成（add_couple_touch 后，逐活动发射） |
| `complete` | 完整 `TripPlanResponse` JSON（含 `warnings` 字段） | 生成完成 |
| `error` | `{ "phase": "...", "message": "..." }` | 异常 |

**客户端消费伪代码**：

```typescript
const eventSource = new EventSource(`/api/plan/${planId}/stream`);

eventSource.addEventListener('step', (e) => {
  const { step, message } = JSON.parse(e.data);
  updateProgress(step, message);
});

eventSource.addEventListener('partial', (e) => {
  const partial = JSON.parse(e.data);
  appendItinerary(partial);
});

eventSource.addEventListener('complete', () => {
  eventSource.close();
  markPlanReady();
});
```

### 3.3 是否引入 WebSocket

**结论：暂不引入。** SSE 的单向推送（server → client）已完全覆盖行程生成的进度通知需求。前端只需消费事件流，无需向服务端持续推送，SSE 更轻量、浏览器原生支持、自动重连。

若未来扩展多用户协作编辑行程（实时同步），再引入 WebSocket。

---

## 4. 数据流图

```
用户浏览器
  │
  │  (1) 填写表单：目的地、日期、预算、偏好
  ▼
┌──────────────────────────────────────────────────────────────────┐
│  TripForm 组件                                                    │
│  - 表单校验                                                        │
│  - POST /api/plan                                                │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             │  (2) plan_id 返回
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  FastAPI Router                                                  │
│  - 创建 TripPlanState                                             │
│  - 投递到 LangGraph Agent                                         │
│  - 返回 plan_id + stream_url                                     │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             │  (3) invoke graph
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  LangGraph Agent                                                 │
│                                                                  │
│  gather_input ──→ fetch_weather ──→ generate_itinerary           │
│               ──→ search_pois   ──→ apply_budget                 │
│                                   ──→ weather_adapt              │
│                                   ──→ add_couple_messages        │
│                                   ──→ finalize_plan              │
│                                                                  │
│  每个 Node 执行时推送 SSE event                                   │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             │  (4) SSE 事件流
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  前端 SSE Consumer (useStream hook)                              │
│  - step → 更新进度条                                              │
│  - partial → 追加行程卡片                                         │
│  - budget_alert → 弹出预算预警                                    │
│  - weather_swap → 标注天气切换                                    │
│  - message → 渲染情侣寄语                                         │
│  - complete → 关闭 EventSource，标记完成                          │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             │  (5) 最终渲染
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  ItineraryCard 组件                                               │
│  - 时间轴布局（上午 / 下午 / 晚间）                                   │
│  - 每个活动：名称、描述、花费、天气图标、情侣寄语                        │
│  - BudgetBar：已消费 / 总预算 进度条                                │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. 目录结构（规划）

```
meng-travel-agent/
├── memory/
│   ├── BOOTSTRAP.md          # 项目总览（恢复上下文用）
│   ├── ROADMAP.md            # 实现路线图
│   ├── ARCHITECTURE.md       # 本文件
│   └── DEPLOY.md             # 部署文档（M7）
├── frontend/
│   ├── src/
│   │   ├── components/       # UI 组件
│   │   ├── pages/            # 页面
│   │   ├── hooks/            # 自定义 hooks
│   │   ├── api/              # API 请求封装
│   │   ├── types/            # TypeScript 类型定义
│   │   └── utils/            # 工具函数
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── vite.config.ts
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI 入口
│   │   ├── config.py         # 配置管理
│   │   ├── api/              # REST + SSE 路由
│   │   ├── agent/            # LangGraph Agent
│   │   │   ├── graph.py
│   │   │   ├── state.py
│   │   │   ├── nodes/
│   │   │   └── prompts/
│   │   ├── models/           # Pydantic 数据模型
│   │   └── services/         # 外部 API 封装
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── docker-compose.yml
└── .gitignore
```

---

## 6. 关键设计决策

| 决策 | 理由 |
|------|------|
| State 用 TypedDict 而非 Pydantic | LangGraph 原生推荐 TypedDict + Annotated，与 add_messages reducer 兼容 |
| 天气 + POI 并行查询 | fetch_weather 和 search_pois 无依赖，并行可减少 40% 等待时间 |
| 预算降级在 apply_budget 内部实现为子循环 | 预算可能多次超标（替换后仍超标），内部循环比条件边更简洁 |
| SSE 而非 WebSocket | 单向推送足够，SSE 浏览器原生支持，无需额外库 |
| 前端 Vite 代理后端 | 开发环境免 CORS 配置，生产环境由 Nginx 反向代理 |

### 6.1 V3 对话记忆的决策（2026-10-16）

| 决策 | 理由 |
|------|------|
| 会话与消息存 **PostgreSQL**，而非 Redis | Redis 的 30 分钟 TTL 意味着"明天回来"从零开始；且它是当时唯一的会话存储、却在本机因 RESP3 握手失败而全程静默降级。会话迁 PG 后 Redis 零消费者，故整体移除（`requirements`/`compose`/`env`）。**触发条件**：多 worker 部署时才为 SSE 事件扇出（`plan_streams` 是进程内存）与共享限流计数重新引入 broker，与聊天记忆无关 |
| 长期记忆用 **结构化存储 + SQL 召回**，不用 pgvector | L1–L3 的事实都是可结构化/可确定的：摘要是文本、画像是固定 schema、情节是"最近 N 个 plan + 反馈聚合"。真正需要 embedding 的只有模糊语义召回（L4），而那时 `tsvector`/`pg_trgm` 往往已经够用 |
| 存储层**同步驱动 + `asyncio.to_thread`** | psycopg 异步模式不支持 Windows 默认的 `ProactorEventLoop`；P0.2 的约束是"不阻塞事件循环"，线程卸载等价且跨平台 |
| 会话/槽位历史**先落 user 消息再调模型** | 浏览器在回复返回前关页时，用户那句话不丢；水合时发现"末尾 user 无回复"即提供"重新生成" |
| `message_id` **唯一约束**做幂等 | 客户端重试（断网、刷新后重试）不会把同一句话写两遍 |
| 活动会话存 **sessionStorage**，localStorage 只存种子/缓存/client_id | 两个标签页打开同一会话会互相把对方轮次插进同一份记录，必须按标签隔离；localStorage 只负责"新标签页从哪继续"与首屏秒下 |
| 问候语是**前端本地播种**，不进服务端记录 | 它是 UI 招呼而非对话内容；写入会污染 L0 窗口与摘要。代价：刷新后若已有真实对话，问候不再出现（与主流对话产品一致） |
| 前端零依赖 store 检查（`npm run check:store`） | 无 vitest/jest，而 tsc+build 抓不到"问候出现两次"这类状态缺陷；用 vite 自带的 esbuild 打包 store 在 node 里断言，零新增依赖。局限：测不到 React effect 接线与网络路径 |
