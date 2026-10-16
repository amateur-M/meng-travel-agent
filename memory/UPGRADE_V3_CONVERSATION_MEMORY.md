## V3 升级：对话记忆与持久化（设计与执行计划）

> 本文是设计稿 + 可跟踪执行计划。目标：让 CoupleTrip 首先是一个**能正常对话**的 Agent，
> 并把对话与状态**真实持久化**（当前环境下持久化层实际全部失效，见 §1.4）。
> 任务带唯一 ID + 状态，进度以本文表格为准。
>
> **v2 修订（2026-10-16）**：初版只做了「最近 N 轮进 prompt」这一层，把"长期记忆"与
> "pgvector"混为一谈写进了非目标，**既没有真正的长期记忆，对话恢复也漏了几类中断场景**。
> 本次补齐 §3 记忆分层、§4 恢复矩阵，并重排任务。

---

## 0. 进度总览

### 状态图例
- ⬜ 待开始　🔄 进行中　✅ 完成　⏸ 阻塞　⭐ 必做　○ 可裁剪

| 阶段 | 目标 | 状态 | 完成度 |
|------|------|------|--------|
| **P0 环境与地基** | 修复静默降级，让持久化真实生效 | 🔄 | 4/5（T0.2 待你跑初始化脚本） |
| **P1 短期记忆与真对话（L0）** ⭐ | 多轮上下文 + 真回答 + 会话落库 | ✅ | 6/6 |
| **P2 长期记忆（L1/L2/L3）** | 滚动摘要 + 跨会话画像 + 情节召回 | ✅ | 5/5 |
| **P3 对话恢复与前端** ⭐ | 刷新/中断/多标签恢复 + 会话切换 | ✅ | 7/7 |
| **P4 收尾** | 文档、冒烟、回归 | 🔄 | 进行中 |

> 硬门槛：每阶段结束须「后端 pytest 全绿 + 前端 `tsc -b && vite build` 通过」。
> 本机未安装 Playwright 浏览器，E2E 不作为本轮的验收手段（见 §7）。
> **可裁剪**：P2 整体可后置，不阻塞 P1/P3；P1+P3 即"可正常对话且不丢对话"的最小可用集。
>
> **执行结果（2026-10-16）**：P0.1/P0.3/P0.4/P0.5 与 P1/P2/P3 全部完成；
> 后端 **409 passed + 2 skipped**，前端 build 通过 + `npm run check:store` 49/49。
> 期间发现两处必须记录的设计修正，见 §11。

---

## 1. 现状诊断（基于真实代码与环境实测）

### 1.1 Agent 没有对话记忆

| 事实 | 证据 |
|------|------|
| 历史被写入但**从未被读取** | `services/session_store.py:97` 定义了 `get_history()`，全仓库 grep 只有定义、**零调用点** |
| LLM 只收到单轮输入 | `services/llm.py:182` 只构造 `[SystemMessage, HumanMessage]` 两条消息，无 history 参数 |
| `handle_chat` 的 prompt 只有槽位 + 当前消息 | `agents/conversation.py`：`user_prompt = f"已有槽位: {existing_slots}\n用户消息: {message}"` |

**后果**：多轮指代全部失效。用户说"那改成三天呢""换一个便宜点的"时，模型看不到上一轮。
**且槽位只在单个 session 内有效**——开新会话即从零开始，上次说过的"女朋友不吃辣""我们住上海"全部遗忘。

### 1.2 `question` 意图不真回答

`_mock_handle` 对信息类问题回固定话术（"好问题～不过我更擅长帮你规划行程"），
且**有 LLM key 时也走同一个结构化 JSON 调用**，没有为"回答旅行知识"设计过自由文本调用。
这是"不像正常对话 Agent"的主因。

### 1.3 前端只持久化了一个 session_id

| 状态 | 存放位置 | 刷新后 |
|------|----------|--------|
| `sessionId` | `sessionStorage`（按标签页、关标签即失） | 保留（同标签内） |
| `messages` | 内存（zustand） | **丢失** |
| `slots` | 内存 | **丢失**（后端 Redis 里有，但前端不读） |
| `planRequest` | 内存 | **丢失** |

`services/chat.ts` 只有 `postChat`，没有任何"读取历史"的调用——后端也没有这个端点。

### 1.4 ⚠️ 两个持久化后端在当前环境下**全部静默失效**

本地实测（临时脚本已删除）：

```
pg_dsn configured:    True
plan save:   False          ← PlanStore 全部返回失败
plan get:    False
plan list:   False
redis slots:   {}
redis history: []
```

- **PostgreSQL**：`localhost:5432` 有真实 `postgres` 进程在监听，但
  `coupletrip` 角色 **password authentication failed** → `PlanStore` 所有方法走 `except` 分支。
- **Redis**：`localhost:6379` 有真实 `redis-server` 进程，但不支持 `HELLO` 命令
  （RESP3 握手，Redis 6+ 才有）→ `redis-py 8.1` 连不上 → `SessionStore` 全部降级。

**这才是"对话记忆没做"的完整答案**：即使代码里已有的槽位记忆与行程持久化，
在**当前环境里也一次都没真正生效**，而优雅降级把故障藏成了 warning 日志。
Docker 未安装，`docker-compose.yml` 里的 `db`/`redis` 服务在本机跑不起来。

### 1.5 Redis 当前是"零收益的故障面"

`session_store` 的**唯一**消费者是 `agents/conversation.py`（3 处调用）；限流器
`main.py:43` 的 `Limiter(...)` **未配置 `storage_uri`**，即 slowapi 用的是进程内存，
与 Redis 无关。所以今天 Redis 只为聊天槽位服务，而它还是坏的。

### 1.6 E2E 用例因 P1.3 路由变更全部失效

P1.3 把 `/` 改成 Chat 页、表单移到 `/form`，但 `frontend/e2e/full_flow.spec.ts`
5 个用例仍 `page.goto("/")` 并断言只存在于 `/form` 的"定制情侣行程"与"生成行程"。
**执行计划里"既有 E2E 不破坏"的说法与代码不符。** 本机 Playwright 浏览器未安装，当前无法运行。

### 1.7 ✅ 双问候 bug（本轮已修复）

**根因**：`main.tsx:7` 使用 `React.StrictMode`，开发模式会**双调用挂载 effect**；
`Chat.tsx` 的问候 effect 依赖闭包里的 `initialized`/`messages`（两次调用间不会重新渲染，
两个值都是陈旧值），于是问候被追加两次。

**修复**：问候下沉为 store 的幂等 action `ensureGreeting()`，守卫读 `get()` 的**实时状态**。
已用 esbuild+node 直接驱动 store 验证：双调用 / 三次调用 / reset 后重播种均只产生 1 条。

---

## 2. 目标与非目标

### 目标
1. **对话可用（L0）**：多轮上下文进 prompt；信息类问题由 LLM 结合历史真回答。
2. **长期记忆（L1–L3）**：会话内滚动摘要、跨会话结构化画像、历史行程与反馈的情节召回。
3. **对话持久化**：会话与消息落 PostgreSQL，跨刷新、跨天、跨标签页可回看。
4. **会话可切换**：会话列表（新建/切换/重命名/删除）。
5. **恢复能力**：刷新、关页、中断、多标签、后端重启、跨天回来都不丢或能明确恢复。
6. **持久化真实生效且可见**：环境可达；失败不再静默（健康检查 + 启动告警）。

### 非目标（明确边界，避免范围蔓延）
- **向量检索 / 语义召回（L4）**：本轮不做 pgvector。注意——这与"长期记忆"**不是**同一件事：
  L1–L3 全部用**结构化存储 + SQL 召回**实现，不需要 embedding。只有当出现
  "找一家像上次那家安静的咖啡馆"这类**模糊语义**需求时才需要 L4，届时先用
  PostgreSQL 全文检索（`tsvector`）或 `pg_trgm` 兜底，仍不必上 pgvector。
- 对话回复的流式输出（SSE 已用于行程规划；对话本轮仍是整段返回）
- 多用户体系与鉴权模型扩展（见 §3.5 的身份口径）
- 多 worker 部署下的 Redis 化改造（见 §6.1 的触发条件）

---

## 3. 记忆分层设计

初版只做了 L0。完整的分层与归属如下：

| 层 | 名称 | 内容 | 存放 | 注入方式 | 本轮 |
|----|------|------|------|----------|------|
| **L0** | 工作记忆 | 最近 N 轮原文 | 内存窗口（源：`chat_messages`） | 真实多轮消息 | ⭐ 必做 |
| **L1** | 会话内长期记忆 | 超出窗口历史的滚动摘要 | `chat_sessions.summary` | 拼进 system prompt | ⭐ 必做 |
| **L2** | 跨会话画像 | 出发地/预算区间/偏好/节奏/忌口/同行人 | `user_profiles` 表 | system prompt 的"已知偏好"段 | ○ 建议 |
| **L3** | 情节记忆 | 历史行程、去过的目的地、活动级 👍/👎 | `plans` + `plan_feedback`（已有表！） | system prompt 的"过往行程"段 | ○ 建议 |
| **L4** | 语义检索 | 模糊语义召回 | pgvector / tsvector | — | ❌ 延后 |

设计要点：
- **L1 的触发**：当 `chat_messages` 条数超过窗口（10 轮）时，把"即将滑出窗口"的旧消息
  交给一次 LLM 调用压缩成摘要，写回 `chat_sessions.summary`（增量合并，不是每次全量重算）。
  调用对用户不可见，失败不影响回复（降级为"无摘要"）。
- **L2 的提取**：复用 `postprocess_slots` 的确定性规则 + 一次结构化 LLM 提取，写入固定 schema 的
  JSONB。**画像只增不删**，同一字段以最新值为准，冲突时保留新旧两个值并在 prompt 里标注
  （避免"预算 5000"被一次口误永久覆盖）。
- **L3 的召回**：纯 SQL——最近 5 个已完成 plan 的目的地/日期 + `plan_feedback` 聚合。
  这让 P2.3 建好但**只被离线脚本使用**的反馈表第一次进入在线链路。
  同时支撑"上次你们去了大理，这次要不要换个地方？"这类主动共情。

### 3.5 身份口径（需要你确认）
应用没有用户体系。L2 画像需要一个稳定 key，三个选项：
1. **客户端 id**：localStorage 生成 UUID，随请求带走（多设备不共享，但零改动接入鉴权）
2. **单一全局画像**：单人部署，一张表一行（最简单，换浏览器也共享）
3. 未来接入鉴权后再挂 `user_id`
本轮建议 **选项 1**，并在 `user_profiles` 表预留 `user_id` 列以便将来迁移。

---

## 4. 对话恢复矩阵

初版只覆盖了"刷新后水合"，以下中断场景是缺口。⭐ = 本轮必做。

| # | 场景 | 初版 | 本轮设计 |
|---|------|------|----------|
| 1 | 刷新页面 | ✅ 水合 messages/slots | 水合 `messages` + `slots` + `plan_request` |
| 2 | 关标签页重开 | ⚠️ sessionStorage 会丢 | localStorage 存"上次活动会话"，新标签据此恢复 |
| 3 | 切换会话 | ✅ 列表 | 同上 |
| 4 | **会话已删除/DB 清空，但本地仍指向旧 id** | ❌ 未处理 | 水合 404 → 静默新建会话 + 问候，不留白屏 |
| 5 | ⭐ **发消息后、回复返回前关页/崩溃** | ❌ 未处理（回复后才落库） | **先落 user 消息，回复到达再补 assistant**；水合时发现"末尾 user 无回复"→ 显示"重新生成"入口 |
| 6 | ⭐ **网络重试导致重复消息** | ❌ 未处理 | 客户端生成 `message_id`，服务端 `chat_messages.message_id UNIQUE` + `ON CONFLICT DO NOTHING` 幂等 |
| 7 | **多标签页同一会话并发写** | ❌ 未处理（localStorage 共享会串） | **本标签活动会话存 sessionStorage**（多标签隔离），localStorage 只存"上次活动 + 列表缓存"；监听 `storage` 事件刷新列表 |
| 8 | 行程生成中刷新 | ✅ `?plan_id` + GET stream 重放 | 不变 |
| 9 | 从 `/result` 返回 Chat | ✅ 内存态保留 | 需审计"重新规划"不得清空会话（P3 任务） |
| 10 | 后端重启（PG 在） | ✅ | 会话/消息/槽位全在 PG，恢复 |
| 11 | **跨天回来（>30min）** | ❌ Redis TTL 30min 即丢 | 迁 PG 后永久保留，正是"正常该有的持久化" |
| 12 | 生成中的 plan 跨 worker | ❌ `plan_streams` 是**进程内存**（`main.py:179`） | 本轮不修，记为已知限制（见 §6.1） |

---

## 5. 架构设计

### 5.1 数据模型（PostgreSQL，与 `plans` 同库）

```sql
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id   TEXT PRIMARY KEY,
    title        TEXT,
    summary      TEXT,                                    -- L1 滚动摘要
    slots        JSONB NOT NULL DEFAULT '{}'::jsonb,
    plan_request JSONB,
    last_plan_id TEXT,
    client_id    TEXT,                                    -- §3.5 身份口径
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id         BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    message_id TEXT UNIQUE,                               -- 恢复矩阵 #6 幂等键
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_profiles (                -- L2 跨会话画像
    client_id  TEXT PRIMARY KEY,
    user_id    TEXT,                                      -- 预留，将来接鉴权
    profile    JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages (session_id, id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated ON chat_sessions (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_client  ON chat_sessions (client_id, updated_at DESC);
```

### 5.2 存储层：`services/conversation_store.py`

**必须异步**。V2 的 P0.2 专门把 LLM 调用改成 `async def` 以避免阻塞事件循环，
而现有 `PlanStore` 用的是**同步** `ConnectionPool`，却在 async 端点里直接调用——这是遗留不一致。
新层用 `psycopg_pool.AsyncConnectionPool` + `await`，全程不阻塞。

方法集：`create_session / get_session / list_sessions / rename_session / delete_session /
append_message(幂等) / get_messages / get_recent_messages / update_slots /
set_summary / get_profile / merge_profile / set_last_plan / health`

**失败不静默**（与现状的关键差异）：`health()` 返回真实连接状态，供 `/health` 暴露。

### 5.3 LLM 记忆层

- `acall_llm(..., history: list[dict] | None = None)`：最近 N 轮按真实
  `HumanMessage/AIMessage` 插到 `SystemMessage` 之后。窗口：最近 **10 轮**或约 2000 token；
  单条截断 2000 字符。
- 新增 `acall_llm_text(...)`：返回**纯文本**，用于自由问答与摘要生成；`acall_llm` 保持严格 JSON。
- **system prompt 组装顺序**（重要，决定记忆如何被使用）：
  ```
  [角色与规则] + [L2 已知偏好] + [L3 过往行程] + [L1 会话摘要] + [最近 N 轮真实消息]
  ```

### 5.4 `handle_chat` 新流程

```
1. 读会话：slots + summary + 最近 N 轮 history；读 L2 画像、L3 历史行程
2. 组装 system_prompt（§5.3 顺序）
3. 先落库 user 消息（幂等，message_id）        ← 恢复矩阵 #5
4. Call 1（总是）：意图 + 槽位 + modify_patch（结构化 JSON，带 history）
5. 分支：
   ├─ intent ∈ {question, greeting} → Call 2：acall_llm_text 真回答
   └─ 其余 → 用 Call 1 返回的 reply 文案；模型没给文案时用确定性模板兜底（不额外调用）
6. 落库 assistant 回复（以 `<user_message_id>:reply` 为键，整轮幂等）；
   更新 slots / updated_at；首条实质消息生成标题
7. 若溢出的消息满 4 条 → 触发 L1 摘要更新（失败不影响回复）
8. 若本轮出现可入库的画像信息（出发地/节奏/偏好/预算区间/忌口）→ 合并进 L2
```

### 5.5 REST API（全部走 `verify_api_key`）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/chat` | 契约基本不变；新增 `message_id`/`client_id`，带 history、落库、真回答 |
| `GET` | `/api/chat/sessions` | 会话列表（分页，`updated_at` 倒序，含标题/预览/消息数） |
| `GET` | `/api/chat/sessions/{id}` | 会话详情（slots + summary + plan_request + last_plan_id） |
| `GET` | `/api/chat/sessions/{id}/messages` | 完整对话记录（分页） |
| `PATCH` | `/api/chat/sessions/{id}` | 重命名 |
| `DELETE` | `/api/chat/sessions/{id}` | 删除会话（级联消息） |
| `GET` | `/api/profile` | L2 画像读取（前端可展示/纠正） |
| `PATCH` | `/api/profile` | L2 画像手工修正（"记住我不吃辣"） |
| `GET` | `/api/chat/recall` | L3 情节召回预览（历史行程摘要，供 UI 展示） |

### 5.6 前端状态与持久化

**存储分工（修正初版）**：

| 键 | 位置 | 理由 |
|----|------|------|
| 本标签活动会话 `coupletrip.active_session` | `sessionStorage` | 多标签隔离（恢复矩阵 #7） |
| 上次活动会话 `coupletrip.last_session` | `localStorage` | 新标签/关页重开的恢复种子（#2） |
| 会话列表缓存 `coupletrip.sessions_cache` | `localStorage` | 首屏秒开，随后被服务端刷新 |
| 客户端 id `coupletrip.client_id` | `localStorage` | §3.5 身份 |

**水合流程**：
```
挂载 → 取 active(sessionStorage) ?? last(localStorage)
  ├─ 命中 → GET /sessions/{id}/messages + GET /sessions/{id} + GET /profile
  │          → 水合 messages/slots/planRequest（hydrating 期间不 ensureGreeting）
  │          → 若 404：清本地指针，落回下面"未命中"分支（恢复矩阵 #4）
  │          → 若末尾是"无回复的 user 消息"：展示"重新生成"（#5）
  └─ 未命中 → ensureGreeting()（幂等，已实现）
```

**UI**：左侧会话列表（桌面常驻、移动端抽屉）+「新对话」+ 当前会话高亮 + 重命名/删除；
Chat 头部显示会话标题；画像可折叠展示并允许纠正。

---

## 6. 两个取舍：我的建议

### 6.1 Redis 去留 → **建议移除，但记录重新引入的触发条件**

**建议移除**，理由（§1.5 已用证据支撑）：
1. Redis 的唯一消费者是聊天槽位存储，而槽位迁 PG 后它**零消费者**；
2. 限流器未用 Redis（slowapi 走进程内存），移除不改变限流行为；
3. 它当前是**坏的**（RESP3 握手失败），保留一个静默失败的依赖正是这次踩的坑；
4. 少一个存储面 = 少一类"测试全绿但功能全废"的可能。

**但这不是说 Redis 没价值**。它真正的价值场景今天还没到，且**不在聊天记忆里**：
- `main.py:179` 的 `plan_streams` 是**进程内存**，多 worker 下"重连到同一个流"会失效；
- slowapi 的内存计数器在多 worker 下也是各算各的。

→ **触发条件**：一旦要以多 worker 部署（`uvicorn --workers N`），就需要 Redis（或等价 broker）
来做 SSE 事件扇出与共享限流计数。届时 Redis 是为**流式与限流**引入的，与聊天记忆无关。
建议把这句话写进 DEPLOY.md，避免以后又出现"为聊天加 Redis"的误解。

如果你已经确定近期就要上多 worker，那更划算的顺序是：**先修协议**（`protocol=2` 关掉 RESP3
握手，或升级到 Redis ≥6）**并保留服务**，一次把 fan-out 改造也做掉；否则就按建议移除。

### 6.2 前端测试框架 → **建议先零依赖方案，等需要测组件再上 vitest**

分三层对待：
1. **纯 store 逻辑**（问候幂等、patch 合并、水合后的状态映射）：用 vite 自带的 esbuild
   把 `chatStore.ts` 打成 CJS，node 里直接断言，加一个 `npm run check:store`。
   **零新增依赖**，本轮修双问候时已经用它跑通了（§1.7）。
2. **React effect 接线**（如"问候只在组件里追加一次"）：这个**零依赖方案测不到**——
   我这次验证的是 store 幂等，不是 effect 本身。防线是：(a) 约定"问候/消息变更只写在 store 里，
   组件不直接改 messages"，(b) E2E。
3. **真正需要 vitest 的信号**：当我们开始测 React 组件渲染、hook、或要 mock axios 的
   水合时序时。到那时引入 vitest + jsdom 才划算；现在为她上框架属于过早。

**同时提一个反向建议**：E2E 那 5 个用例现在既失效又跑不了，而接下来要大改路由、水合、
会话切换——这类改动最容易悄悄破坏整体流程。安装 Playwright 浏览器是一次性一条命令、
约 150MB，能立刻把"失效的 5 个用例 + 新增的持久化用例"变成真门槛。你之前选了不装，
我尊重这个决定，但如果你愿意，这是本轮**性价比最高**的一项验证投入。

---

## 7. 执行计划

### P0 环境与地基（不修则任何记忆功能都无法验证）

| 任务 ID | 内容 | 状态 | 产出 |
|---------|------|------|------|
| T0.1 ⭐ | 修复双问候：`ensureGreeting()` 幂等 action | ✅ | chatStore.ts + Chat.tsx（build + node 断言通过） |
| T0.2 ⭐ | 本地 PostgreSQL 可达：创建 `coupletrip` 角色/库（或更正 `PG_DSN`），附脚本 + DEPLOY 步骤 | ⏸ 脚本已就绪，**待你执行** | `backend/scripts/init_local_db.sql` + DEPLOY.md |
| T0.3 ⭐ | 存储收敛：移除聊天链路 Redis（`session_store.py` 退役、compose 去 redis、requirements 去依赖） | ✅ | 见 §11：**并入 P1 执行**（需先有新存储接管，否则中间态是坏的） |
| T0.4 ⭐ | 消除静默降级：`/health` 暴露存储状态；启动时一次性 ERROR 告警 | ✅ | main.py + storage + `test_storage_health.py`（8 例） |
| T0.5 | 修复 E2E 路由失效（`/` → `/form`），保持 CI 用例有效 | ✅ | e2e/full_flow.spec.ts（另加问候回归守卫；本机无浏览器未执行） |

**P0 出口**：`/health` 显示 postgres ok（**待 T0.2**）；`PlanStore` 真实往返成功（**待 T0.2**）；pytest 全绿 ✅。
**顺带修复**：存储诊断原本只报 `PoolTimeout`，现在报真实原因（`password authentication failed ...`），
并把连接失败超时从 30s 降到 5s（整套测试 37s → 18s）。

### P1 短期记忆与真对话（L0）⭐

| 任务 ID | 内容 | 状态 | 产出 |
|---------|------|------|------|
| T1.1 ⭐ | §5.1 三张表 DDL + `ConversationStore`（幂等 append、优雅降级、`health()`） | ✅ | services/conversation_store.py |
| T1.2 ⭐ | `acall_llm(history=...)` + 新增 `acall_llm_text()` | ✅ | services/llm.py |
| T1.3 ⭐ | `handle_chat` 接入 history + 先落 user 消息 + 落 assistant + 自动标题 | ✅ | agents/conversation.py |
| T1.4 ⭐ | question/greeting 走第二调用真回答（含 mock 兜底话术升级） | ✅ | agents/conversation.py + prompts/chat_reply_prompt.md |
| T1.5 ⭐ | 会话 CRUD + messages 端点（§5.5 前 6 个） | ✅ | main.py + schemas/chat.py |
| T1.6 ⭐ | 后端测试：多轮记忆传入、真回答分支、CRUD、幂等、PG 不可达降级 | ✅ | test_conversation_memory.py(23) / test_chat_sessions_api.py(23) / test_conversation_e2e.py(14) / test_conversation_store_pg.py |

**P1 出口**：两轮对话可复现"第二轮引用第一轮" ✅ —— **不必等数据库**：
`tests/test_conversation_e2e.py` 用内存假 store 驱动 ASGI 应用，端到端断言了
"turn 2 的 history 里真的有 turn 1，且不含当前轮"；真实 PostgreSQL 往返 ⏸（待 T0.2）；
`message_id` 去重 ✅（整轮幂等：assistant 回复以 `<user_message_id>:reply` 为键）；
pytest 全绿 ✅。

### P2 长期记忆（L1/L2/L3）

| 任务 ID | 内容 | 状态 | 产出 |
|---------|------|------|------|
| T2.1 ⭐ | L1 滚动摘要：`summary` + `summary_message_count` 游标 + 增量压缩 + 注入 prompt | ✅ | agents/memory.py + conversation_store |
| T2.2 ○ | L2 画像：`user_profiles` + 提取/合并规则 + `GET/PATCH /api/profile` | ✅ | agents/memory.py + main.py |
| T2.3 ○ | L3 情节召回：最近行程 + `plan_feedback` 聚合进 prompt + `GET /api/chat/recall` | ✅ | agents/memory.py + conversation.py |
| T2.4 ○ | 记忆预算：窗口 10 轮(20 条)、**整块 ≤8000 字符**、单条截断 2000 字符、溢出满 4 条才摘要、组装顺序固化 | ✅ | agents/memory.py + services/llm.py（整块上限为首轮漏做、本轮补齐，见 §11.6） |
| T2.5 ○ | 记忆测试：摘要触发、画像合并与冲突、召回渲染、prompt 组装顺序 | ✅ | tests/test_memory.py（43 例） |

**P2 出口**：长对话仍能引用早期内容 ✅（摘要+游标机制与注入均有单测）；新会话继承画像 ✅；
prompt 能说出"上次去过哪" ✅。
**设计落实**：L1–L3 **全部用结构化存储 + SQL 召回，无 embedding** —— 这是"要有长期记忆"与
"V2 拒绝 pgvector"并不冲突的关键（初版把两者混为一谈，见 §11）。

### P3 对话恢复与前端 ⭐

| 任务 ID | 内容 | 状态 | 产出 |
|---------|------|------|------|
| T3.1 ⭐ | 存储分工（§5.6）+ 水合 messages/slots/planRequest + `hydrating` 态 | ✅ | chatStore.ts |
| T3.2 ⭐ | 会话列表 UI：新建/切换/重命名/删除（桌面常驻 + 移动端抽屉） | ✅ | components/Chat/SessionList.tsx |
| T3.3 ⭐ | 恢复硬化：404 → 新建会话；末尾无回复的 user 消息 → "重新生成"；`message_id` 幂等 | ✅ | 恢复矩阵 #4/#5/#6（`/messages` 现返回 `message_id` 作为重试依据） |
| T3.4 ⭐ | 多标签一致性：本标签 sessionStorage + `storage` 事件刷新列表 | ✅ | 恢复矩阵 #7 |
| T3.5 ⭐ | 页面切换审计：Chat↔loading↔result↔form，"重新规划"不得清空会话 | ✅ | 恢复矩阵 #9（hydrate 按 page load 缓存，不覆盖内存态） |
| T3.6 ○ | 会话↔行程关联：`last_plan_id` 回写与列表展示 | ✅ | main.py + plan.ts + SessionList（可点"查看行程"） |
| T3.7 ⭐ | 前端类型 + `tsc -b && vite build` 通过；`npm run check:store` | ✅ | package.json + scripts/check-chat-store.cjs（49/49） |

**P3 出口**：恢复矩阵 1–7、9 逐条手工验证 ⏸（待 T0.2 后按 §8 清单执行）；build 通过 ✅。

### P4 收尾

| 任务 ID | 内容 | 状态 | 产出 |
|---------|------|------|------|
| T4.1 | 文档：ARCHITECTURE API/数据模型、DEPLOY 环境与 Redis 触发条件、PROGRESS/GOALS/BOOTSTRAP 记 V3 | ✅ | memory/*.md |
| T4.2 | 手工冒烟清单（§8）执行并记录 | ⏸ 待 T0.2 | memory/DEPLOY.md |
| T4.3 | 回归：pytest 全绿 + build 通过 + check:store | ✅ | 409 passed + 2 skipped；build 通过；49/49 |

---

## 8. 验收方式（Playwright 浏览器未安装的替代方案）

1. **后端集成测试（主力）**：FastAPI `TestClient` + 依赖覆盖，驱动**真实多轮对话**，
   断言"第二轮受第一轮影响"、消息落库条数与顺序、`message_id` 幂等、会话 CRUD、
   摘要触发、画像合并、召回内容。这是"记忆真的生效"最直接的证据。
2. **真实存储往返测试**：PG 可达时跑真实 CRUD；**不可达则 `skip` 并显式标记**，
   不允许静默通过——避免重演 §1.4 的"测试全绿但功能全废"。
3. **手工冒烟清单**（写进 DEPLOY.md，由你执行勾选）：
   - [ ] 发两轮消息，第二轮能引用第一轮
   - [ ] 提问旅行知识，得到实质回答而非固定话术
   - [ ] 刷新页面：对话记录与槽位仍在
   - [ ] 关标签页重开：仍回到原会话
   - [ ] 新建第二个会话，切换回来内容不串（画像共享、对话不共享）
   - [ ] 删除当前会话后自动落到新会话
   - [ ] 发消息后立刻刷新：能看到自己那条消息，并有"重新生成"入口
   - [ ] 两个标签页开同一会话：互不串写（#7）
   - [ ] 20 轮以上长对话：仍能引用早期内容（L1）
   - [ ] 新会话里 agent 知道上次去过的目的地（L3）
   - [ ] Chat → 生成行程 → 结果页 → 返回：对话未丢

**E2E**：T0.5 修复路由后保持 CI 可跑；本机不执行，不在本轮验收范围。

---

## 9. 风险与取舍

| 风险 | 处理 |
|------|------|
| 记忆变长导致 token 成本与延迟上升 | L0 窗口 10 轮 + 单条 2000 字符；L1 增量摘要；规划类不走第二次调用 |
| L1 摘要**有损**，可能丢掉关键细节 | 摘要与最近 10 轮**并存**（不是替换）；槽位/画像这类关键信息走结构化存储，不依赖摘要 |
| L2 画像写错且长期污染后续对话 | 只增不删 + 冲突保留新旧两值并在 prompt 标注 + `PATCH /api/profile` 人工纠正 |
| L3 召回让 prompt 变长 | 只取最近 5 个 plan + 反馈聚合，硬上限 |
| 移除 Redis 会动 compose 与依赖 | 单独一个提交便于回滚；Redis 数据本就 TTL 30min、可丢弃；触发条件写入文档 |
| `ConversationStore` 异步化与同步 `PlanStore` 风格不一致 | 新层必须异步（P0.2 的教训）；**已在收尾时一并修掉 PlanStore**：原先它在 async 端点里被直接调用，PG 不可达时会把事件循环冻住整个 5s 池超时；现全部经 `asyncio.to_thread`，并由 `tests/test_event_loop.py` 用循环延迟度量守住 |
| 本地 PG 凭据不明 | T0.2 先做连通性确认，再决定"建角色"还是"改 DSN" |
| 自动标题质量 | 先用"首条用户消息截断 20 字"，不额外花 LLM 调用 |
| 多 worker 下 in-flight SSE 仍会断 | 本轮不修，记录为已知限制（§6.1 触发条件） |

---

## 10. 与既有计划的关系

| 项 | 既有状态 | 本计划处理 |
|----|----------|-----------|
| P1.1 Redis 会话槽位 | ✅ 已交付 | **T0.3 收敛**：会话改 PG，Redis 在聊天链路退役 |
| P1.1 消息历史写入 | ✅ 已交付但从未被读取 | T1.3 真正接入 prompt（`get_history` 从死代码变成主路径） |
| P1.3 Chat UI | ✅ 已交付 | T3.1–T3.6 补持久化、会话列表、切换与恢复硬化 |
| P0.1 行程持久化 | ✅ 代码完成 | T0.2/T0.4 修环境可达性与静默降级（当前实际未生效） |
| P2.3 用户反馈表 | ✅ 已交付但仅离线脚本使用 | T2.3 首次进入在线链路（L3 召回） |
| P3.2 可观测性 | ✅ structlog + /metrics | T0.4 借 `/health` 暴露存储状态 |
| E2E 5 用例 | 文档称"不破坏"，实际全失效 | T0.5 修复路由 |

---

## 11. 执行中的设计修正（必须记录）

### 11.1 存储层不能用 psycopg 异步模式 —— 改线程卸载

**计划原文**：「**必须异步**。用 `psycopg_pool.AsyncConnectionPool` + `await`，全程不阻塞事件循环。」

**实测结果**：在 Windows 上直接失败 ——

```
InterfaceError: Psycopg cannot use the 'ProactorEventLoop' to run in async mode.
Please use a compatible event loop, for instance by running
'asyncio.run(..., loop_factory=asyncio.SelectorEventLoop(...))'
```

psycopg 的异步模式依赖 `add_reader`/`add_writer`，而 Windows 默认的
`ProactorEventLoop` 不提供；Windows 又是本项目的主要开发平台。若坚持异步驱动，
本机与 uvicorn 默认配置下整套对话持久化都会失效。

**修正**：改用**同步** `ConnectionPool`，所有 DB 调用经 `asyncio.to_thread` 卸载到
工作线程。P0.2 的要求是"**不阻塞事件循环**"，而不是"必须用异步驱动"——
线程卸载同样满足，且在 Linux / Windows 行为一致。公开 API 仍是 `async def`，
调用方无需感知线程。

**顺带**：一开始为异步池写了「按事件循环缓存池」的逻辑（异步连接绑定创建它的
loop）。改成同步池后该问题不存在，这段复杂度已删除。

### 11.2 T0.3（移除 Redis）并入 P1 执行

计划把"移除聊天链路 Redis"放在 P0，但 Redis 是当时**唯一**的会话存储：
先删掉它、再在 P1 建新存储，中间态是坏的（会话无处可存），提交历史里会出现
一个不可用的版本。

**修正**：P0 只做"让存储状态可见"（T0.4），保留仍可用的降级路径；等 P1 的
PostgreSQL 存储接管后再删 Redis —— 该提交因此是自洽的（"会话从 Redis 迁到
PostgreSQL"），每个提交都是绿的。

### 11.3 记忆窗口的单位

计划写「最近 10 轮」，而 `get_recent_messages(limit=N)` 的单位是**消息条数**，
一次"轮"是 user+assistant 两条。初版 `HISTORY_TURNS = 10` 实际只给了 5 轮。

**修正**：明确为 `HISTORY_EXCHANGES = 10` / `HISTORY_MESSAGES = 20`，摘要触发
与溢出切片都以"消息条数"为准，避免再次混淆。

### 11.4 存储诊断必须报根因

计划的 T0.4 只要求"暴露状态"。实测发现 `pool.open(wait=True)` 失败时抛的是
`PoolTimeout: pool initialization incomplete after 5 sec`，而真实原因是
`password authentication failed for user "coupletrip"` —— 前者把排查引向了连接超时
这个错误方向。现在失败时会用一次直接连接取出根因再上报。

### 11.5 未闭环项（需要你执行）

> 2026-10-16 补充：为降低对 T0.2 的依赖，新增了**不依赖数据库的端到端测试**
> （`tests/test_conversation_e2e.py`，用 `InMemoryConversationStore` 驱动真实 ASGI 应用，
> 并断言该假实现覆盖了真实 store 的每个公开方法以防腐化）。因此下列内容已可在无 PG 时验证：
> 两轮对话按序落库、第二轮看到第一轮、重放不重复、修改轮合并进槽位、画像跨会话、
> 超窗口写摘要、会话 CRUD 与级联删除。
> **仍然只有 T0.2 能验证的**：真实 PostgreSQL 的读写往返（含 JSONB、唯一约束、级联、
> 真实并发下的增量摘要游标），以及浏览器里的刷新/多标签/跨天表现。

1. **T0.2**：本机 PostgreSQL 18.6（`D:\Software\Postgresql18`）对所有连接要求
   scram-sha-256，而 `.env` 里的 `coupletrip / coupletrip_dev` 认证失败。已在
   `backend/scripts/init_local_db.sql` 写好幂等初始化，需以超级用户执行一次：
   ```
   "D:\Software\Postgresql18\bin\psql.exe" -U postgres -h 127.0.0.1 -f backend/scripts/init_local_db.sql
   ```
   执行前 `tests/test_conversation_store_pg.py` 会以
   「PostgreSQL unavailable — chat persistence NOT verified」**显式跳过**（不会静默通过）。
2. **T3.5 / T4.2**：恢复矩阵中依赖真实数据库的条目（刷新恢复、跨天、多标签、
   会话切换）需在 T0.2 完成后按 §8 的手工冒烟清单逐条勾选。
3. **E2E**：本机未安装 Playwright 浏览器，T0.5 修好的 5+2 个用例仅在 CI 生效。

### 11.6 首轮漏做、第二轮补齐：L0 整块预算

T2.4 写的是"记忆预算：**token 上限**、摘要触发阈值、单条截断、组装顺序固化"，
但首轮只实现了单条截断（2000 字符），**整块上限没做**，而 ARCHITECTURE 与
PROGRESS 已按"有预算"描述。窗口 20 条 × 单条 2000 字符最坏约 4 万字符，
每轮请求都要发出去 —— 属于计划未交付 + 文档与代码不符。

第二轮补齐：`MAX_HISTORY_TOTAL_CHARS = 8000`，超预算时**从最旧的一条开始丢**
（旧内容已由 L1 摘要承载；丢掉紧跟当前消息的那一轮会恰好破坏"那改成三天呢"这类追问）。
当前用户消息永不被预算裁掉。由 `tests/test_llm_history.py` 16 例覆盖
（单条截断、整块上限、保留最新/丢弃最旧、时序、角色映射、异常行容忍、当前消息不截断）。

同时修正另一处文档精度问题：原先写"规划类 → 确定性模板"，实际是**优先用 Call 1
返回的 reply 文案、模型没给文案时才用模板兜底**；"不额外调用"这一半才是准确的。
