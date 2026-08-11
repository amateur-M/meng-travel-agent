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
│   ├── agents/                      # LangGraph Agent 引擎
│   │   ├── __init__.py
│   │   ├── state.py                 # AgentState TypedDict 定义
│   │   ├── graph.py                 # LangGraph 图构建 + 编译
│   │   └── nodes/                   # 各 Node 实现（M1 填充）
│   │       └── __init__.py
│   ├── tools/                       # LangChain Tools
│   │   └── __init__.py              # 天气、地图、搜索工具（M2 填充）
│   ├── prompts/                     # LLM Prompt 模板
│   │   └── __init__.py
│   ├── schemas/                     # Pydantic 数据模型
│   │   └── __init__.py              # API 请求/响应 schema（M1 填充）
│   └── tests/                       # 后端测试
│       └── __init__.py
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
