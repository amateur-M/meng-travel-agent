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
│   │   └── qweather_auth.py         # QWeather JWT/API Key 鉴权
│   ├── agents/                      # LangGraph Agent 引擎
│   │   ├── __init__.py
│   │   ├── state.py                 # AgentState TypedDict 定义
│   │   ├── graph.py                 # LangGraph 图构建 + 编译
│   │   └── nodes/                   # 各 Node 实现（M1 完成）
│   │       ├── __init__.py
│   │       ├── parse_input.py
│   │       ├── fetch_weather.py
│   │       ├── search_poi.py
│   │       ├── search_food.py
│   │       ├── plan_itinerary.py
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
│       ├── components/              # UI 组件（M3 填充）
│       ├── pages/                   # 页面级组件
│       ├── hooks/                   # 自定义 hooks（M6 SSE 等）
│       ├── services/                # API 调用封装（axios）
│       ├── stores/                  # Zustand 状态管理
│       └── types/                   # TypeScript 类型定义
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
