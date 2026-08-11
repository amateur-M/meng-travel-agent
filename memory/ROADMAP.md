## 项目概述

**项目名称**：情侣旅游规划 Agent（CoupleTrip）

**一句话描述**：AI 驱动的旅游规划助手，根据日期、出发地、目的地、天气、景点、美食、预算与偏好，自动生成可执行的情侣行程。

**核心理念**：浪漫节奏（不赶场、留白时间）、预算透明（实时累计 + 超预算降级）、天气自适应（雨天室内方案）、情侣共情（每个节点附寄语）。

---

## 里程碑总览

| 里程碑 | 名称 | 核心交付 | 预计工期 |
|--------|------|----------|----------|
| M0 | 项目初始化与工程搭建 | 前后端骨架可运行 | 2 天 |
| M1 | 后端核心 Agent 引擎 | LangGraph 行程生成链路跑通 | 5 天 |
| M2 | 外部 API 集成层 | 天气 + 地图 POI 数据可用 | 3 天 |
| M3 | 前端基础 UI | 输入表单 + 行程卡片展示 | 4 天 |
| M4 | 预算透明与天气自适应 | 花费累计、降级方案、天气切换 | 4 天 |
| M5 | 节奏控制与情侣向体验 | 三档节奏 + 每节点情侣寄语 | 4 天 |
| M6 | 实时交互（SSE 流式） | 行程逐步生成、流式展示 | 3 天 |
| M7 | 测试、部署与收尾 | Docker 化 + E2E + 文档 | 3 天 |

---

## M0：项目初始化与工程搭建

**目标**：搭建前后端项目骨架，配置开发环境与工具链，确保两端均可独立启动。

**涉及模块**：
- 前端：React 18 + TypeScript + Tailwind CSS + Framer Motion + Vite
- 后端：Python 3.13 + FastAPI + LangChain + LangGraph + Poetry

**预计产出文件**：
- `frontend/package.json`、`frontend/tsconfig.json`、`frontend/tailwind.config.ts`、`frontend/vite.config.ts`
- `frontend/src/main.tsx`、`frontend/src/App.tsx`、`frontend/index.html`
- `backend/pyproject.toml`、`backend/app/main.py`、`backend/app/config.py`
- `.gitignore`、`.env.example`

**验收标准**：
- `cd frontend && npm install && npm run dev` 启动开发服务器，浏览器可见 Hello 页面
- `cd backend && poetry install && poetry run uvicorn app.main:app --reload` 启动后端，`/health` 返回 200
- Tailwind CSS 在开发模式下正常工作
- 前端可成功请求后端 `GET /health`

---

## M1：后端核心 Agent 引擎

**目标**：基于 LangGraph 实现行程规划的核心链路，给定输入参数即可输出结构化行程 JSON。

**涉及模块**：
- `graph.py`：LangGraph 图定义与编译
- `state.py`：TripPlanState 状态定义
- `nodes/`：各 Node 实现文件（gather_input、fetch_weather、search_pois、generate_itinerary、apply_budget、weather_adapt、add_couple_messages、finalize_plan）
- `prompts/`：LLM Prompt 模板
- `models/`：Pydantic 数据模型（TripPlan、DayPlan、Activity、Budget 等）

**预计产出文件**：
- `backend/app/agent/__init__.py`
- `backend/app/agent/state.py`
- `backend/app/agent/graph.py`
- `backend/app/agent/nodes/__init__.py`
- `backend/app/agent/nodes/gather_input.py`
- `backend/app/agent/nodes/generate_itinerary.py`
- `backend/app/agent/nodes/apply_budget.py`
- `backend/app/agent/nodes/weather_adapt.py`
- `backend/app/agent/nodes/add_couple_messages.py`
- `backend/app/agent/nodes/finalize.py`
- `backend/app/agent/prompts/__init__.py`
- `backend/app/agent/prompts/system.py`
- `backend/app/models/trip.py`
- `backend/app/models/activity.py`
- `backend/tests/test_agent.py`

**验收标准**：
- 输入：`{ destination: "大理", start_date: "2026-09-01", end_date: "2026-09-03", budget: 5000, preferences: ["浪漫", "美食"] }`
- 输出结构化的 `TripPlan` JSON，包含每天上午/下午/晚间活动、预估花费、情侣寄语
- 不依赖真实外部 API（该阶段使用 mock 数据），纯 Agent 链路跑通
- 单元测试覆盖核心 Node 逻辑

---

## M2：外部 API 集成层

**目标**：对接天气 API 和地图 API，替换 M1 中的 mock 数据。

**涉及模块**：
- `weather_service.py`：天气查询（和风天气 / OpenWeatherMap）
- `map_service.py`：POI 搜索 + 地理编码（高德 / Google Maps）
- `services/cache.py`：API 响应缓存层（降低调用量）

**预计产出文件**：
- `backend/app/services/__init__.py`
- `backend/app/services/weather.py`
- `backend/app/services/map.py`
- `backend/app/services/cache.py`
- `backend/tests/test_weather.py`
- `backend/tests/test_map.py`

**验收标准**：
- 给定城市名，可获取未来 7 天天气预报
- 给定城市 + 关键词（如"餐厅"），可返回 POI 列表（名称、坐标、评分、人均消费）
- 缓存层正常工作：相同查询 5 分钟内不重复调用外部 API
- 全部单测通过，使用 pytest + vcrpy 录制外部 API 响应

---

## M3：前端基础 UI

**目标**：实现行程输入表单 + 行程卡片展示，完成前后端联调。

**涉及模块**：
- `TripForm`：日期、出发地、目的地、预算、偏好标签输入
- `ItineraryCard`：每日行程卡片（时间轴 + 活动列表）
- `BudgetBar`：预算使用进度条
- `api/`：前端 API 封装层

**预计产出文件**：
- `frontend/src/pages/Home.tsx`
- `frontend/src/components/TripForm.tsx`
- `frontend/src/components/ItineraryCard.tsx`
- `frontend/src/components/BudgetBar.tsx`
- `frontend/src/components/ActivityItem.tsx`
- `frontend/src/api/plan.ts`
- `frontend/src/types/trip.ts`

**验收标准**：
- 在 TripForm 中填入参数并提交，能成功调用 `POST /api/plan`
- 返回的行程 JSON 以时间轴卡片形式展示
- 卡片包含：日期、天气图标、活动列表、预估花费、情侣寄语
- Tailwind 响应式适配：移动端单列、桌面端双列

---

## M4：预算透明与天气自适应

**目标**：实现预算实时累计 + 超预算自动降级 + 雨天自动切换室内方案。

**涉及模块**：
- `BudgetCalculator`：后端预算核算与降级算法
- `WeatherAdapter`：天气条件匹配与方案切换
- 前端 `BudgetAlerts`：超预算提示与降级方案展示

**预计产出文件**：
- `backend/app/agent/nodes/budget_engine.py`
- `backend/app/agent/nodes/weather_engine.py`
- `frontend/src/components/BudgetAlerts.tsx`
- `frontend/src/components/WeatherBadge.tsx`

**验收标准**：
- 每项活动标注预估花费，行程顶部显示总预算与已消费进度
- 当累计花费超过预算 90% 时触发黄色预警，超过 100% 时自动生成降级方案（替换高价餐厅/景点）
- 查询到雨天时自动将户外景点替换为室内备选（博物馆、咖啡馆、手工坊等），并在 UI 中标注切换原因
- 高温天（>35°C）自动将户外活动安排在上午或傍晚

---

## M5：节奏控制与情侣向体验

**目标**：上午/下午/晚间三档节奏控制 + 每个活动节点生成情侣寄语。

**涉及模块**：
- `RhythmController`：节奏引擎（每档最多 2 个活动 + 留白时间）
- `CoupleMessageGenerator`：基于活动类型 + 目的地氛围生成共情文案
- 前端 `CoupleMessage` 组件：特殊视觉样式展示寄语

**预计产出文件**：
- `backend/app/agent/nodes/rhythm_control.py`
- `backend/app/agent/nodes/couple_message.py`
- `backend/app/agent/prompts/couple.py`
- `frontend/src/components/CoupleMessage.tsx`

**验收标准**：
- 每天行程严格分为 上午 / 下午 / 晚间 三档，每档最多 2 个活动
- 活动之间有明确的留白时间（如"午后漫步"、"洱海边发呆"）
- 每个活动附带一句情侣寄语（如"和你一起看苍山雪，山不说话，但我懂它"），风格温暖不油腻
- 寄语根据活动类型（自然/美食/人文/冒险）变化语气和内容

---

## M6：实时交互（SSE 流式输出）

**目标**：行程生成过程通过 SSE 逐步推送到前端，用户实时看到规划进度。

**涉及模块**：
- `SSEHandler`：FastAPI SSE endpoint
- `useStream`：前端自定义 hook，消费 SSE 事件
- `ProgressIndicator`：进度展示组件

**预计产出文件**：
- `backend/app/api/sse.py`
- `frontend/src/hooks/useStream.ts`
- `frontend/src/components/ProgressIndicator.tsx`
- `frontend/src/components/StreamingItinerary.tsx`

**验收标准**：
- 用户提交规划请求后，页面显示 "正在查询天气..." → "正在搜索景点..." → "正在生成行程..." → "正在添加寄语..."
- 每个阶段完成后对应卡片逐步出现，不是一次性全部渲染
- SSE 断连后自动重试
- 流式输出与最终结果一致

---

## M7：测试、部署与收尾

**目标**：全链路 E2E 测试覆盖，Docker 一键部署，完善项目文档。

**涉及模块**：
- `tests/e2e/`：Playwright E2E 测试
- `Dockerfile.frontend`、`Dockerfile.backend`
- `docker-compose.yml`
- `.github/workflows/`：CI 流水线

**预计产出文件**：
- `tests/e2e/full_flow.spec.ts`
- `Dockerfile.frontend`
- `Dockerfile.backend`
- `docker-compose.yml`
- `.github/workflows/ci.yml`
- `memory/DEPLOY.md`

**验收标准**：
- `docker-compose up` 一键启动全栈，浏览器访问即可使用
- Playwright E2E 覆盖完整流程：输入 → 生成 → 展示 → 降级触发
- CI 流水线自动运行 lint + test + build

---

## 里程碑依赖关系

```
M0 ──→ M1 ──→ M3 ──→ M4 ──→ M5 ──→ M6 ──→ M7
         │                      │
         └──→ M2 ──────────────┘
```

M1 和 M2 可并行开发（M1 用 mock 数据，M2 是纯服务层）。M3 依赖 M1 完成后才可联调。M4/M5 依赖 M2 的真实数据。M6 依赖 M3 的 UI 骨架。
