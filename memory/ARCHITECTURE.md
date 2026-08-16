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
| `gather_input` | 解析并校验用户输入，补全默认值 | 原始请求 | 规范化后的 state |
| `fetch_weather` | 调用天气 API，获取行程日期范围内的天气 | destination, dates | weather_data |
| `search_pois` | 调用地图 POI API，搜索景点 + 餐厅 + 室内备选 | destination, preferences | poi_attractions, poi_restaurants, poi_indoor |
| `generate_itinerary` | 调用 LLM 生成初步行程骨架 | weather + pois + 偏好 | itinerary (draft) |
| `apply_budget` | 核算每项花费，超预算时生成降级方案 | itinerary + budget | itinerary (adjusted), budget_summary |
| `weather_adapt` | 根据天气条件调整行程（雨天/高温切换） | itinerary + weather_data | itinerary (weather-adjusted) |
| `add_couple_messages` | 为每个活动生成情侣寄语 | itinerary | itinerary (with messages) |
| `finalize_plan` | 最终校验、格式化、持久化 | itinerary | 最终 TripPlan |

### 2.3 Edge / 流程编排

```
                  ┌──────────────┐
                  │  START       │
                  └──────┬───────┘
                         │
                  ┌──────▼───────┐
                  │ gather_input │
                  └──────┬───────┘
                         │
              ┌──────────┼──────────┐
              │                     │
       ┌──────▼───────┐     ┌───────▼──────┐
       │ fetch_weather│     │ search_pois  │   ← 并行
       └──────┬───────┘     └───────┬──────┘
              │                     │
              └──────────┬──────────┘
                         │
                  ┌──────▼───────────┐
                  │generate_itinerary│
                  └──────┬───────────┘
                         │
                  ┌──────▼───────┐
                  │ apply_budget │
                  └──────┬───────┘
                         │
                  ┌──────▼───────┐
                  │weather_adapt │
                  └──────┬───────┘
                         │
                  ┌──────▼───────────┐
                  │  add_couple_msgs │
                  └──────┬───────────┘
                         │
                  ┌──────▼───────┐
                  │ finalize_plan│
                  └──────┬───────┘
                         │
                  ┌──────▼───────┐
                  │     END      │
                  └──────────────┘
```

**条件分支说明**：
- `apply_budget` 内部：若累计花费 ≤ 预算，直接通过；若 > 预算，进入降级子流程（替换高价项目 → 重新核算 → 最多重试 2 次）
- `weather_adapt` 内部：若全部晴天，无操作；若有雨天/高温，触发方案切换子流程
- 未来可扩展 `router` 条件边实现更复杂的分支（如用户中途修改偏好后重新规划）

---

## 3. 前后端通信接口

### 3.1 REST API

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/api/plan` | 提交行程规划请求，返回 `plan_id` |
| `GET` | `/api/plan/{plan_id}` | 查询已完成的行程详情 |
| `GET` | `/api/plan/{plan_id}/stream` | SSE 端点，流式推送规划进度 |
| `GET` | `/api/plan/history` | 历史行程列表（分页） |
| `DELETE` | `/api/plan/{plan_id}` | 删除历史行程 |

**POST /api/plan 请求体**：

```json
{
  "origin": "北京",
  "destination": "大理",
  "start_date": "2026-09-01",
  "end_date": "2026-09-03",
  "budget": 5000,
  "preferences": ["浪漫", "美食", "自然"],
  "pace": "轻松"
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

### 3.2 SSE 协议

端点：`GET /api/plan/{plan_id}/stream`

事件类型：

| event | data | 说明 |
|-------|------|------|
| `step` | `{ "step": "fetch_weather", "message": "正在查询大理天气..." }` | 当前步骤 |
| `partial` | `{ "day_index": 0, "period": "morning", "activities": [...] }` | 部分行程数据 |
| `budget_alert` | `{ "current": 5200, "limit": 5000, "suggestions": [...] }` | 预算预警 |
| `weather_swap` | `{ "original": {...}, "replacement": {...}, "reason": "雨天切换" }` | 天气方案切换 |
| `message` | `{ "day": 1, "activity": "洱海骑行", "text": "和你一起..." }` | 情侣寄语生成 |
| `complete` | `{ "plan_id": "uuid", "status": "completed" }` | 生成完成 |
| `error` | `{ "code": "...", "message": "..." }` | 异常 |

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
