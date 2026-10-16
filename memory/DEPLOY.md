# 部署文档

## 一、本地开发

### 0. 数据库（V3 起为必需）

对话记忆与行程持久化都用 PostgreSQL。首次需要建角色与库，脚本是幂等的，
可以重复执行；它只建/重置 `coupletrip` 角色与库，**不会动其他数据库**：

```bash
# 会交互式询问 postgres 超级用户密码（密码不进 shell 历史）
psql -U postgres -h 127.0.0.1 -f backend/scripts/init_local_db.sql
# Windows 上 psql 的完整路径例：
# "D:\Software\Postgresql18\bin\psql.exe" -U postgres -h 127.0.0.1 -f backend/scripts/init_local_db.sql
```

验证：`curl http://localhost:8000/health` 应返回
`storage.postgres.connected = true` 且 `storage.chat.connected = true`；
若有任一为 `false`，`error` 字段会带上真实原因（认证失败/库不存在等），
`status` 也会变成 `degraded`。

> 未初始化时**不会崩**：应用照常对话，只是不持久化。后端启动时会打一条 ERROR
> 日志，两个存储的真实状态也能在 `/health` 看到 —— 这是 V3 专门修掉的问题
> （此前每次写入静默返回 False，功能坏了与"还没存过东西"在观测上没区别）。

> **不再需要 Redis**（V3 起）。旧版本用 Redis 存会话，30 分钟 TTL 且本机因
> RESP3 握手失败而全程降级；会话迁到 PostgreSQL 后 Redis 已无消费者，依赖与
> compose 服务均已移除。多 worker 部署时才需要重新引入 broker，见 §七。

### 1. 后端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # 填入 API key
uvicorn main:app --reload --port 8000
```

健康检查：`curl http://localhost:8000/health`

### 2. 前端

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173 (Vite 代理 /api → :8000)
```

### 3. 前端检查脚本

```bash
cd frontend
npm run build          # tsc -b + vite build
npm run check:store    # 零依赖 store 行为检查（问候幂等、client_id、patch 合并等）
```

`check:store` 用 vite 自带的 esbuild 把 `chatStore` 打成 CJS 在 node 里断言
（并 stub 掉 `services/chat`），用来补 `tsc`/`build` 抓不到的状态类缺陷。
当前 49 项，覆盖：

- 纯本地逻辑：问候幂等、`client_id` 稳定落盘、`applyPatch` 合并、`newSession`、`reset`
- 水合恢复：还原对话与槽位/planRequest/关联行程；同一会话不重复拉取
- 恢复矩阵 #4：本地指针指向已删会话 → 清指针并新建（不留白屏）
- 恢复矩阵 #5/#6：末尾无回复 → 置"重新生成"；重试**复用同一 `message_id`**
  且不会多出一条用户消息
- 会话切换与删除回退；离线时回退到本地列表缓存

它**测不到** React effect 接线（双问候 bug 就出在那里）与真实网络/数据库路径 ——
那两类由 §五 的手工冒烟清单覆盖。

## 二、Docker 一键部署

```bash
docker compose up -d --build
```

| 服务 | 端口 | 说明 |
|------|------|------|
| db | 5432 | PostgreSQL 16（行程 + 对话持久化，volume `pgdata`） |
| backend | 8000 | FastAPI + LangGraph（uvicorn 直跑） |
| frontend | 80 | Nginx 托管 Vite 静态产物 + 反代 `/api` 到 backend:8000 |

启动后访问 `http://localhost` 即可使用。

容器带 healthcheck，backend `depends_on: db (service_healthy)`、frontend
`depends_on: backend (service_healthy)`，保证依赖就绪后再启动。

**环境变量**通过 `backend/.env` 注入（compose `env_file`）。`DEFAULT_LLM_PROVIDER`、
`PG_DSN`、`POSTGRES_PASSWORD` 可在 compose 层覆盖。

### 重新构建

```bash
docker compose up -d --build        # 代码变更后重建
docker compose logs -f backend      # 查看后端日志
docker compose down                 # 停止（数据保留在 pgdata volume）
docker compose down -v              # 停止并清空数据
```

## 三、E2E 测试 (Playwright)

```bash
cd frontend
npm install
npx playwright install --with-deps chromium   # 首次安装浏览器（约 150MB）
npm run e2e                                     # 运行 e2e
```

前提：后端在 `localhost:8000` 运行且数据库已初始化（或通过 `E2E_BASE_URL` 指向已部署实例）。

路由契约与覆盖场景（`e2e/full_flow.spec.ts`）：

| 路由 | 页面 |
|------|------|
| `/` | Chat 对话页（默认入口） |
| `/form` | 旧表单页（`TripForm`） |
| `/loading` | 规划进度 |
| `/result` | 行程结果 |

1. 对话页：问候只出现 1 条（回归守卫）、输入区可见
2. 表单页加载并展示表单
3. 提交默认表单 → Loading 页 → 结果页
4. 结果页展示天数 / 预算 / 寄语
5. 重新规划返回首页（`/`，现为对话页）
6. 低预算触发降级（结果正常渲染）

> 注意：P1.3 把 `/` 改成对话页后，这 5 个用例曾全部失效（仍访问 `/` 并断言表单
> 元素），V3 的 T0.5 已修正。

## 四、CI 流水线 (`.github/workflows/ci.yml`)

push / PR 到 main 时自动触发三阶段：

| Job | 内容 |
|-----|------|
| `backend-test` | `pip install` + `pytest`（无 API key，走 mock 降级路径） |
| `frontend-build` | `npm ci` + `tsc -b`（app + node + **e2e** 三个项目）+ `npm run check:store` + `vite build` |
| `docker-build` | 依赖前两个 job 通过后构建前后端 Docker 镜像 |

> `tsc -b` 而非 `tsc --noEmit`：根 `tsconfig.json` 自身没有文件（`files: []`），
> 非 build 模式不会跟进 project references，`tsc --noEmit` 实际什么也不检查。
> build 模式才会依次检查 `tsconfig.app.json`（src）、`tsconfig.node.json`
> （vite 配置）、`tsconfig.e2e.json`（Playwright 配置 + `e2e/`）。
> E2E 用例因此在本机无需浏览器也能被类型检查覆盖。

## 五、手工冒烟清单（对话记忆与恢复）

Playwright 浏览器未安装时，下列行为只能手工验证。**每条都对应一个真实缺陷或
恢复场景**，请在数据库初始化后逐条勾选并在本文件记录结果。

标注 `[自动]` 的条目已由 `npm run check:store` 覆盖（客户端逻辑层），手工执行时
只需确认它们在**真实浏览器 + 真实后端**下的表现一致。

- [ ] 发两轮消息，第二轮能引用第一轮（L0 记忆）
- [ ] 问一个旅行知识问题，得到实质回答而非固定话术（真回答）
- [ ] 刷新页面：对话记录与槽位仍在
- [ ] 关标签页重开：仍回到原会话
- [ ] 新建第二个会话，切换回来内容不串（画像共享、对话不共享）
- [ ] 删除当前会话后自动落到新会话（或下一个会话）`[自动：回退逻辑]`
- [ ] 发消息后立刻刷新：能看到自己那条消息，并出现"重新生成"入口 `[自动：置位逻辑]`
- [ ] 点"重新生成"：得到回复，且**用户消息没有重复** `[自动：同 message_id 复用]`
- [ ] 两个标签页开同一会话：互不串写
- [ ] 20 轮以上长对话：仍能引用早期内容（L1 摘要）
- [ ] 新会话里 agent 知道上次去过的目的地（L3 情节记忆）
- [ ] Chat → 生成行程 → 结果页 → 返回：对话未丢；侧边栏显示"已生成行程"

## 六、前置条件

- 后端至少配置一个 LLM provider 的 API key（`OPENAI_API_KEY` / `DEEPSEEK_API_KEY` / `QWEN_API_KEY` / `KIMI_API_KEY`），否则走 mock 降级行程
- 天气与地图 API 缺失时自动降级为 mock，不阻断流程（`warnings` 字段会记录降级原因）
- PostgreSQL 未就绪时不阻断对话，但**不持久化**（`/health` 会显示 `degraded`）
- 生产部署建议把 `backend/.env` 改为容器编排平台的 secrets 注入

## 七、多 worker 部署前必读

当前 `plan_streams`（SSE 事件队列）与限流计数器都是**进程内存**：以
`uvicorn --workers N` 启动时，"断线重连到同一个流"会落到没有该队列的 worker，
限流也会各算各的。

要上多 worker，需要引入 broker（Redis 或等价物）做 **SSE 事件扇出 + 共享限流计数**。
注意：这与对话记忆无关 —— 会话与消息已在 PostgreSQL 里，跨 worker 天然一致。

## 八、项目交付清单

| 交付物 | 路径 | 状态 |
|--------|------|------|
| 后端 Dockerfile | `backend/Dockerfile` | ✅ |
| 前端 Dockerfile | `frontend/Dockerfile` | ✅ (多阶段 build → nginx) |
| 前端 Nginx 配置 | `frontend/nginx.conf` | ✅ (SPA fallback + `/api` 反代 + SSE 关闭缓冲) |
| Docker Compose | `docker-compose.yml` | ✅ (db + healthcheck + 依赖顺序) |
| 本地库初始化脚本 | `backend/scripts/init_local_db.sql` | ✅ (幂等，V3 新增) |
| .dockerignore | `backend/.dockerignore`、`frontend/.dockerignore` | ✅ |
| CI 流水线 | `.github/workflows/ci.yml` | ✅ (test → build → docker) |
| Playwright E2E | `frontend/e2e/full_flow.spec.ts` + `playwright.config.ts` | ✅ (本机无浏览器，CI 生效) |
| 前端 store 检查 | `frontend/scripts/check-chat-store.cjs` + `npm run check:store` | ✅ (V3 新增) |
| 部署文档 | `memory/DEPLOY.md` | ✅ 本文件 |
