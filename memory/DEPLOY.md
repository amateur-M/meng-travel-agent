# 部署文档 (M7)

## 一、本地开发

### 后端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # 填入 API key
uvicorn main:app --reload --port 8000
```

健康检查：`curl http://localhost:8000/health`

### 前端

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173 (Vite 代理 /api → :8000)
```

## 二、Docker 一键部署

```bash
docker compose up -d --build
```

| 服务 | 端口 | 说明 |
|------|------|------|
| backend | 8000 | FastAPI + LangGraph（uvicorn 直跑） |
| frontend | 80 | Nginx 托管 Vite 静态产物 + 反代 `/api` 到 backend:8000 |

启动后访问 `http://localhost` 即可使用。

容器带 healthcheck，frontend `depends_on: backend (service_healthy)`，保证后端就绪后才启动前端。

**环境变量**通过 `backend/.env` 注入（compose `env_file`）。`DEFAULT_LLM_PROVIDER` 可在 compose 层覆盖。

### 重新构建

```bash
docker compose up -d --build        # 代码变更后重建
docker compose logs -f backend      # 查看后端日志
docker compose down                 # 停止
```

## 三、E2E 测试 (Playwright)

```bash
cd frontend
npm install
npx playwright install --with-deps chromium   # 首次安装浏览器
npm run e2e                                     # 运行 e2e
```

前提：后端在 `localhost:8000` 运行（或通过 `E2E_BASE_URL` 指向已部署实例）。

覆盖场景（`e2e/full_flow.spec.ts`）：
1. 首页加载并展示表单
2. 提交默认表单 → Loading 页 → 结果页
3. 结果页展示天数 / 预算 / 寄语
4. 重新规划返回首页
5. 低预算触发降级（结果正常渲染）

## 四、CI 流水线 (`.github/workflows/ci.yml`)

push / PR 到 main 时自动触发三阶段：

| Job | 内容 |
|-----|------|
| `backend-test` | `pip install` + `pytest`（无 API key，走 mock 降级路径） |
| `frontend-build` | `npm ci` + `tsc --noEmit` + `vite build` |
| `docker-build` | 依赖前两个 job 通过后构建前后端 Docker 镜像 |

## 五、前置条件

- 后端至少配置一个 LLM provider 的 API key（`OPENAI_API_KEY` / `DEEPSEEK_API_KEY` / `QWEN_API_KEY` / `KIMI_API_KEY`），否则走 mock 降级行程
- 天气与地图 API 缺失时自动降级为 mock，不阻断流程（`warnings` 字段会记录降级原因）
- 生产部署建议把 `backend/.env` 改为容器编排平台的 secrets 注入

## 六、项目交付清单

| 交付物 | 路径 | 状态 |
|--------|------|------|
| 后端 Dockerfile | `backend/Dockerfile` | ✅ |
| 前端 Dockerfile | `frontend/Dockerfile` | ✅ (多阶段 build → nginx) |
| 前端 Nginx 配置 | `frontend/nginx.conf` | ✅ (SPA fallback + `/api` 反代 + SSE 关闭缓冲) |
| Docker Compose | `docker-compose.yml` | ✅ (healthcheck + 依赖顺序) |
| .dockerignore | `backend/.dockerignore`、`frontend/.dockerignore` | ✅ |
| CI 流水线 | `.github/workflows/ci.yml` | ✅ (test → build → docker) |
| Playwright E2E | `frontend/e2e/full_flow.spec.ts` + `playwright.config.ts` | ✅ |
| 部署文档 | `memory/DEPLOY.md` | ✅ 本文件 |
