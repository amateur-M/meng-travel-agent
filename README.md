# CoupleTrip — 情侣旅游规划 Agent

AI 驱动的旅游规划助手。以**对话为唯一主入口**：在聊天里说清日期、出发地、目的地、预算与偏好，
即可生成可执行的情侣行程（浪漫节奏、预算透明、天气自适应、每个活动附情侣寄语）。
行程生成后直接落在对话内，点「查看完整行程」才进入 `/result` 全屏详情。

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 18 + TypeScript + Tailwind CSS + Framer Motion + Zustand + Vite |
| 后端 | Python 3.13 + FastAPI + LangChain + LangGraph |
| 存储 | PostgreSQL（行程、会话/消息、画像、反馈）；**不需要 Redis** |
| LLM | OpenAI GPT-4o / DeepSeek / Qwen / Kimi（`DEFAULT_LLM_PROVIDER` 切换） |
| 外部 API | 和风天气 QWeather（天气）、高德地图（POI / 地理编码） |

## 快速启动

### 0. 数据库（V3 起必需）

对话记忆与行程持久化都依赖 PostgreSQL，首次需初始化角色与库：

```bash
psql -U postgres -h 127.0.0.1 -f backend/scripts/init_local_db.sql
```

脚本幂等，只操作 `coupletrip` 这一个角色与库；自定义密码、`PG_DSN` 写法与
`scram-sha-256` 陷阱见 [`memory/DEPLOY.md`](memory/DEPLOY.md) §一。

> 未初始化时应用**不会崩**，但不会持久化 —— `/health` 会显示 `degraded` 并带上
> 真实原因。这是 V3 专门修掉的「静默降级」问题，别只看应用能启动就以为存储通了。

### 1. 后端

```bash
cd backend
cp .env.example .env          # 填入 LLM / 天气 / 地图 key 与 PG_DSN
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

- `python main.py` 同样可启动：`main.py` 尾部有 `__main__` 块，等价于
  `uvicorn.run("main:app", port=8000, reload=True)`；应用本体由 `create_app()` 装配。
- 本机 `backend/.venv` 由 **uv** 管理且无 pip：补依赖请用
  `uv pip install --python .\.venv\Scripts\python.exe <pkg>`，并让
  `requirements.txt` 与 `pyproject.toml [project.dependencies]` 保持同步。
- 零成本离线演示用 `OFFLINE_MODE=true`（PowerShell：`$env:OFFLINE_MODE='true'`）。
  **不要**把 key 设成空字符串 —— 空环境变量不会覆盖 `.env`
  （pydantic-settings 视其为未设置），曾因此意外发出真实付费请求。

验证：

```bash
curl http://localhost:8000/health   # 恒 200，含 storage.postgres / storage.chat 真实状态
curl http://localhost:8000/ready    # 任一存储不可达返回 503（供编排器摘流）
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173，Vite 代理 /api → :8000
```

打开 `/` 即 Chat 对话页；`/form` 是保留的隐藏批量录入入口，`/result` 为行程详情页。

### 3. Docker（可选）

```bash
docker compose up -d --build   # db + backend + frontend，启动后访问 http://localhost
```

> 本机未安装 Docker，PostgreSQL 18.6 为原生安装 —— 本地开发走上面的 0 / 1 / 2 步即可。
> healthcheck、env 注入与 volume 细节见 `memory/DEPLOY.md` §二。

### 4. 常用检查

```bash
cd backend  && python -m pytest -q   # 后端全量回归
cd frontend && npm run build         # tsc -b && vite build
cd frontend && npm run check:store   # 零依赖 store 行为检查
```

## 项目文档

新会话恢复上下文，按 [`memory/BOOTSTRAP.md`](memory/BOOTSTRAP.md) 末尾的
「恢复上下文步骤」顺序阅读 9 份文档。常用入口：

| 文档 | 内容 |
|------|------|
| [`memory/ARCHITECTURE.md`](memory/ARCHITECTURE.md) | 技术决策、Agent 设计、L0–L3 记忆分层、API 与 SSE 协议 |
| [`memory/ROADMAP.md`](memory/ROADMAP.md) | M0–M7 里程碑与验收标准 |
| [`memory/PROGRESS.md`](memory/PROGRESS.md) | 各里程碑与 V2–V6 完成清单 |
| [`memory/DEPLOY.md`](memory/DEPLOY.md) | 本地 / Docker / E2E / CI 与手工冒烟清单 |
| [`memory/KEY_DECISIONS.md`](memory/KEY_DECISIONS.md) | 关键技术取舍编号记录 |
