## 项目目录结构（实际）

```
meng-travel-agent/
├── memory/                          # 项目记忆（与会话无关的持久化文档）
│   ├── BOOTSTRAP.md                 # 项目总览，新会话恢复入口
│   ├── ROADMAP.md                   # 实现路线图（8 个里程碑）
│   ├── ARCHITECTURE.md              # 系统架构设计
│   ├── PROJECT_STRUCTURE.md         # 本文件 — 目录结构说明
│   ├── KEY_DECISIONS.md             # 关键设计决策记录
│   ├── PROGRESS.md                  # 开发进度追踪
│   └── GOALS.md                     # 当前迭代目标
│
├── backend/                         # Python 后端
│   ├── main.py                      # FastAPI 入口，/health 健康检查
│   ├── pyproject.toml               # Poetry 项目配置 + 依赖声明
│   ├── requirements.txt             # pip 依赖列表（兼容性）
│   ├── .env.example                 # 环境变量模板（API 密钥占位）
│   ├── config/                      # 配置模块
│   │   ├── __init__.py              # 导出 Settings
│   │   └── settings.py             # 集中配置类（env → Python）
│   ├── services/                    # 业务服务层（M2 新增）
│   │   ├── __init__.py
│   │   ├── llm.py                   # LLM 统一调用入口 + mock fallback
│   │   ├── qweather_auth.py         # QWeather JWT/API Key 鉴权
│   │   └── amap.py                  # 高德地图真实 POI/餐厅/路线服务
│   ├── agents/                      # LangGraph Agent 引擎
│   │   ├── __init__.py
│   │   ├── state.py                 # AgentState TypedDict 定义
│   │   ├── graph.py                 # LangGraph 图构建 + 编译
│   │   └── nodes/                   # 各 Node 实现（M1 完成，M5 扩展）
│   │       ├── __init__.py
│   │       ├── parse_input.py
│   │       ├── fetch_weather.py
│   │       ├── search_poi.py
│   │       ├── search_food.py
│   │       ├── plan_itinerary.py
│   │       ├── rhythm_control.py      # M5: 节奏控制（每档≤2活动 + 留白注入）
│   │       ├── budget_check.py
│   │       ├── adapt_weather.py
│   │       ├── add_couple_touch.py
│   │       └── output_format.py
│   ├── tools/                       # LangChain Tools（M2 新增）
│   │   ├── __init__.py              # 导出所有 Tool
│   │   ├── weather_tool.py          # 天气查询（OpenWeatherMap + mock fallback）
│   │   ├── poi_search_tool.py       # 景点搜索（5 城市 mock POI 数据库）
│   │   ├── food_search_tool.py      # 美食搜索（5 城市 mock 餐厅数据库）
│   │   └── maps_tool.py            # 路线规划（Haversine + nearest-neighbor）
│   ├── prompts/                     # LLM Prompt 模板
│   │   ├── __init__.py              # 加载 .md 模板 + M1 内联模板
│   │   ├── parse_input_prompt.md    # 提取结构化旅行参数
│   │   ├── plan_itinerary_prompt.md # 核心行程编排（浪漫节奏）
│   │   ├── couple_copy_prompt.md    # 情侣共情文案生成
│   │   ├── weather_adapt_prompt.md  # 雨天/高温天气自适应
│   │   └── budget_downgrade_prompt.md # 预算超标降级策略
│   ├── schemas/                     # Pydantic 数据模型
│   │   └── __init__.py              # API 请求/响应 schema
│   └── tests/                       # 后端测试
│       ├── __init__.py
│       ├── conftest.py              # 外部 API 隔离 + opt-in 真实测试开关
│       ├── test_state.py
│       ├── test_schemas.py
│       ├── test_prompts.py
│       ├── test_nodes_input.py
│       ├── test_nodes_core.py
│       ├── test_nodes_output.py
│       ├── test_tools.py
│       ├── test_services.py
│       ├── test_qweather_auth.py
│       ├── test_qweather_external_api.py
│       ├── test_qweather_cassettes.py
│       ├── cassettes/
│       │   ├── qweather_city_lookup.yaml
│       │   └── qweather_daily_forecast.yaml
│       └── test_graph.py
│
├── frontend/                        # React 前端
│   ├── index.html                   # HTML 入口
│   ├── package.json                 # 依赖 + 脚本
│   ├── tsconfig.json                # TS 项目引用
│   ├── tsconfig.app.json            # 应用 TS 配置
│   ├── tsconfig.node.json           # Node 端 TS 配置
│   ├── vite.config.ts               # Vite 配置（含代理到后端 8000）
│   ├── tailwind.config.ts           # Tailwind CSS 配置
│   ├── postcss.config.js            # PostCSS 配置
│   ├── public/                      # 静态资源
│   └── src/
│       ├── main.tsx                 # React 入口
│       ├── App.tsx                  # 根组件（React Router 路由）
│       ├── index.css                # Tailwind 指令
│       ├── vite-env.d.ts            # Vite 类型声明
│       ├── components/
│       │   ├── TripForm/            # 行程输入表单
│       │   │   ├── TripForm.tsx
│       │   │   ├── DestinationSelect.tsx
│       │   │   ├── DateRangePicker.tsx
│       │   │   ├── BudgetSlider.tsx
│       │   │   └── PreferenceTags.tsx
│       │   ├── Timeline/            # 行程时间轴（Day 1 → Day N）
│       │   │   └── Timeline.tsx
│       │   ├── TimelineCard/        # 单个活动卡片（M5: 留白 dashed 样式 + CoupleMessage 内联）
│       │   │   └── TimelineCard.tsx
│       │   ├── CoupleMessage/       # M5: 时段差异化情侣寄语内联展示
│       │   │   └── CoupleMessage.tsx
│       │   ├── BudgetBar/           # 预算进度条
│       │   │   └── BudgetBar.tsx
│       │   ├── BudgetAlerts/        # 预算预警与降级说明
│       │   │   └── BudgetAlerts.tsx
│       │   ├── WeatherBadge/        # 天气标识
│       │   │   └── WeatherBadge.tsx
│       │   ├── CoupleQuote/         # 情侣寄语气泡（日级侧边栏）
│       │   │   └── CoupleQuote.tsx
│       │   ├── SSEProgress/         # Agent 进度可视化
│       │   │   └── SSEProgress.tsx
│       │   └── StreamingItinerary/  # M6: 流式行程逐步渲染
│       │       └── StreamingItinerary.tsx
│       ├── pages/
│       │   ├── Home.tsx             # 首页（行程输入）
│       │   ├── PlanResult.tsx       # 行程展示页
│       │   └── Loading.tsx          # 规划中动画页
│       ├── services/
│       │   ├── api.ts               # Axios 实例 + 拦截器
│       │   ├── sse.ts               # SSE 连接管理
│       │   └── plan.ts              # POST /api/plan + 响应归一化
│       ├── stores/
│       │   ├── tripStore.ts         # 表单 / 行程 / 预算状态
│       │   └── uiStore.ts           # 主题 / 动画状态
│       ├── types/
│       │   └── trip.ts              # 前端行程类型定义
│       └── config/
│           └── tripOptions.ts       # 目的地 / 偏好 / 节奏选项
│
├── docker-compose.yml               # Docker 编排
├── .gitignore                       # Git 忽略规则
└── README.md                        # 项目说明
```

## 目录命名对照（实际 vs ARCHITECTURE 规划）

| 实际目录 | 规划目录 | 说明 |
|----------|----------|------|
| `backend/agents/` | `backend/app/agent/` | 目录层级简化，去掉 app 中间层 |
| `backend/config/` | `backend/app/config.py` | 配置独立为包，含 `__init__.py` |
| `backend/schemas/` | `backend/app/models/` | schemas 更明确表示 API 数据模型 |
| `backend/tools/` | `backend/app/services/` | tools 更贴切 LangChain 术语 |
| `frontend/src/services/` | `frontend/src/api/` | services 范围更广，含业务逻辑封装 |
| `frontend/src/stores/` | (未规划) | 新增 Zustand 状态管理层 |

## M2 新增文件清单 (2026-08-11)

| 文件 | 行数 | 说明 |
|------|------|------|
| `tools/weather_tool.py` | ~150 | OpenWeatherMap async + mock fallback, @tool |
| `tools/poi_search_tool.py` | ~200 | 5 城市 × ~10 POI, 偏好过滤, couple_score |
| `tools/food_search_tool.py` | ~130 | 5 城市 × ~5 餐厅, 菜系/预算筛选, atmosphere tags |
| `tools/maps_tool.py` | ~100 | Haversine 距离, nearest-neighbor 路线, 多交通方式预估 |
| `prompts/parse_input_prompt.md` | ~70 | 结构化参数提取, 字段约束, 示例 |
| `prompts/plan_itinerary_prompt.md` | ~130 | 核心编排, 节奏控制, JSON Schema 约束 |
| `prompts/couple_copy_prompt.md` | ~60 | 按活动类型的语气指引, 避免俗套句式, 8-25 字限制 |
| `prompts/weather_adapt_prompt.md` | ~70 | 4 条调整规则（雨/高温/低温/大风）, swaps + time_shifts |
| `prompts/budget_downgrade_prompt.md` | ~80 | 4 级降级策略, impact 分级, 不可降级项列表 |

## QWeather 鉴权新增文件 (2026-08-15)

| 文件 | 说明 |
|------|------|
| `services/qweather_auth.py` | Ed25519 JWT 生成、PEM/JWT/API Key 自动识别、请求头构建 |
| `tests/test_qweather_auth.py` | 鉴权单测：JWT 结构、签名验证、API Key、错误分支 |
| `tests/test_qweather_external_api.py` | 可选的真实 QWeather API 冒烟测试，`QWX_TEST_REAL_API=1` 启用 |

## QWeather vcrpy 测试新增文件 (2026-08-16)

| 文件 | 说明 |
|------|------|
| `tests/test_qweather_cassettes.py` | 离线重放 QWeather GeoAPI / daily forecast HTTP 交互 |
| `tests/cassettes/qweather_city_lookup.yaml` | 城市坐标查询 cassette |
| `tests/cassettes/qweather_daily_forecast.yaml` | 城市查询 + daily forecast cassette |

## M3 前端核心实现文件 (2026-08-18)

| 文件 | 说明 |
|------|------|
| `frontend/src/types/trip.ts` | 行程请求 / 响应、活动、预算、天气、进度类型 |
| `frontend/src/config/tripOptions.ts` | 出发地 / 目的地 / 偏好 / 节奏选项 |
| `frontend/src/services/api.ts` | Axios 实例 + 响应错误归一化 |
| `frontend/src/services/sse.ts` | SSE 连接管理与事件分发 |
| `frontend/src/stores/tripStore.ts` | 表单 / 行程 / 预算 / 规划进度状态 |
| `frontend/src/stores/uiStore.ts` | 主题 / 动画状态 |
| `frontend/src/pages/Home.tsx` | 行程输入首页 |
| `frontend/src/pages/PlanResult.tsx` | 行程时间轴展示页 |
| `frontend/src/pages/Loading.tsx` | 规划中动画页 |
| `frontend/src/components/TripForm/` | 目的地选择、日期范围、预算滑块、偏好标签 |
| `frontend/src/components/Timeline/` | 按 Day 1 → Day N 展开 / 折叠的时间轴 |
| `frontend/src/components/TimelineCard/` | 单个活动卡片 |
| `frontend/src/components/BudgetBar/` | 实时预算进度条 |
| `frontend/src/components/WeatherBadge/` | 晴 / 雨 / 高温天气标识 |
| `frontend/src/components/CoupleQuote/` | 情侣共情文案气泡 |
| `frontend/src/components/SSEProgress/` | Agent 思考过程可视化 |

## M4 真实数据接入 (2026-08-31)

| 文件 | 说明 |
|------|------|
| `backend/services/amap.py` | 高德 Web Service：POI 搜索、驾车路线，城市 adcode 映射 |
| `backend/tools/poi_search_tool.py` | 替换本地 mock 数据库，实时查询高德景点/博物馆 |
| `backend/tools/food_search_tool.py` | 替换本地 mock 数据库，实时查询高德餐饮 |
| `backend/tools/maps_tool.py` | 替换 Haversine 估算，使用高德真实驾车路线 |
| `backend/agents/nodes/search_poi.py` | 移除通用假数据兜底，失败时写入 error |
| `backend/agents/nodes/search_food.py` | 移除通用假数据兜底，失败时写入 error |

## 已删除 mock 文件

- `frontend/src/mocks/trip.ts`（无引用的离线预览 mock）

## M4 新增 / 调整文件清单 (2026-08-31)

| 文件 | 说明 |
|------|------|
| `backend/agents/nodes/budget_check.py` | 预算分级、实际降级替换、`warning_level` / `spending_ratio` |
| `backend/agents/nodes/adapt_weather.py` | 雨天室内切换、高温时段调整、`weather_swaps` 记录 |
| `backend/agents/nodes/output_format.py` | 归一化日期、每日天气、每日花费与天气调整记录 |
| `backend/agents/graph.py` | 预算已降级时直接进入天气自适应，避免撤销降级 |
| `backend/schemas/__init__.py` | 新增 `WeatherSwap`，扩展 `BudgetBreakdown` 与 `TripPlanResponse` |
| `backend/agents/state.py` | 新增 `downgrade_suggestions` 与 `weather_swaps` 状态字段 |
| `frontend/src/components/BudgetAlerts/` | 90% 黄色预警、超预算降级说明 |
| `frontend/src/components/BudgetBar/` | ok / warning / over 三态展示 |
| `frontend/src/components/WeatherBadge/` | 展示天气切换原因 |
| `frontend/src/components/Timeline/` | 按天过滤并传递天气调整记录 |
| `frontend/src/pages/PlanResult.tsx` | 页头增加总预算 / 已花费 / 使用比例 |

## M5 新增 / 调整文件清单 (2026-10-02)

| 文件 | 说明 |
|------|------|
| `backend/agents/nodes/rhythm_control.py` | M5 节奏控制节点：每档≤2活动裁剪 + 留白注入 |
| `backend/agents/graph.py` | 注册 rhythm_control，边改为 plan → rhythm → budget |
| `backend/agents/state.py` | 新增 `rhythm_adjustments` 状态字段 |
| `backend/agents/nodes/output_format.py` | 输出含 `rhythm_adjustments` |
| `backend/agents/nodes/add_couple_touch.py` | 留白模板按时段拆分 + batch prompt 增时段指引 |
| `backend/prompts/couple_copy_prompt.md` | 补充留白时段语气表 + 晚间通用氛围指引 |
| `backend/schemas/__init__.py` | 新增 `RhythmAdjustment` + `TripPlanResponse.rhythm_adjustments` |
| `backend/tests/test_nodes_rhythm.py` | 14 个测试：cap/rest/normalise/node |
| `backend/tests/test_nodes_output.py` | +5 个留白时段寄语测试 + rhythm_adjustments 输出断言 |
| `frontend/src/components/CoupleMessage/CoupleMessage.tsx` | 时段差异化寄语内联组件（金/粉/靛色条） |
| `frontend/src/components/TimelineCard/TimelineCard.tsx` | 引入 CoupleMessage + 留白 dashed 边框 + 隐藏花费 |
| `frontend/src/types/trip.ts` | 新增 `RhythmAdjustment` 接口 |
| `frontend/src/services/plan.ts` | 新增 `normalizeRhythmAdjustments` |

## M6 SSE 流式交互强化新增文件清单 (2026-10-03)

| 文件 | 说明 |
|------|------|
| `backend/main.py` | `_stream_graph` 改用 `stream_mode="updates"`，新增 `_sse`/`_emit_node_events` 发射 7 类事件；删除过时 sync fallback |
| `backend/tests/test_sse.py` | 16 个测试：SSE helper 单测 + 全流集成（事件类型/顺序/complete 结构） |
| `frontend/src/components/StreamingItinerary/StreamingItinerary.tsx` | 流式行程逐步渲染组件（partial 事件 → 逐日逐时段卡片） |
| `frontend/src/services/sse.ts` | `postEventStream` 支持全部 7 类事件 + 断连自动重试（最多 2 次） |
| `frontend/src/stores/tripStore.ts` | 新增 `streamingDays`/`budgetAlert`/`weatherSwaps`/`coupleMessages` 流式状态 |
| `frontend/src/pages/Loading.tsx` | 进度条下方渲染流式行程 + 预算/天气/寄语实时徽章 |
| `frontend/src/types/trip.ts` | 新增 `PartialEvent`/`BudgetAlertEvent`/`WeatherSwapEvent`/`MessageEvent` 类型 |
| `frontend/src/services/plan.ts` | `createPlan` 透传新事件回调 |
