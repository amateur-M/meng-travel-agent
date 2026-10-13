## 对话式 + 向量库升级方案（V2）

> 本文档规划在已交付的 M0–M7 基础上的三项核心升级，并补充作者建议的额外优化。
> 里程碑编号沿用既有 M 序列，扩展为 M8–M10。

---

## 1. 背景与目标

当前产品是一个「表单驱动」的单次规划工具：用户在前端 `TripForm` 一次性填齐 6 个结构化字段，后端 `POST /api/plan` 直接进入 LangGraph 规划管线，SSE 流式返回行程。POI 来源单一（高德 Amap），缺乏语义化精选推荐。

本次升级要解决三个问题：

1. **交互形态**：从固定表单改为对话式，用户用自然语言表达需求，系统从对话中提取参数。
2. **意图识别与槽位填充**：闲聊/通用提问不触发昂贵的规划管线；只有收集到足够必要信息后才启动规划。
3. **POI 参考性**：接入 pgvector 向量库，与高德实时 POI 双源融合，景点推荐更贴合「情侣/浪漫」语义。

---

## 2. 三大优化点设计

### 2.1 对话式交互 + 意图识别（合并为 M8/M9 两条协作轨道）

> 对话前端（M9）依赖对话后端（M8），但二者属同一特性，需协同开发。M8 先行以提供可 curl 验证的接口。

#### 2.1.1 关键决策：双端点而非单端点

不把对话与流式规划塞进同一个 SSE 端点，而是拆为两个职责分明的接口：

| 端点 | 模式 | 用途 | 状态 |
|------|------|------|------|
| `POST /api/chat` | JSON 请求/响应（非流式） | 单轮对话：意图识别 + 槽位提取 + 追问/闲聊回复 | **新增** |
| `POST /api/plan` | SSE 流式 | 规划管线（既有 M1–M6）保持不变 | **保留** |

**理由**：
- 对话轮次是同步、轻量的（一次 LLM 调用），不值得长期占用 SSE 连接。
- 规划管线是重计算、流式增量渲染，已有成熟 SSE 协议，零改动复用。
- 前端状态机显式：收到 `ready=true` 时再发起 `/api/plan`，逻辑清晰、易测试。
- 现有 183 个后端测试与 Playwright E2E 不受影响（`/api/plan` 契约不变）。

#### 2.1.2 意图分类（taxonomy）

一次 `/api/chat` LLM 调用同时产出 `intent` + `slots`（从本条消息提取并与历史合并）+ `reply`：

| intent | 含义 | 处理 | 触发规划？ |
|--------|------|------|-----------|
| `greeting` | 打招呼/闲聊（你好、在吗） | 温暖短回复，不动槽位 | 否 |
| `question` | 通用旅行知识提问（大理几月最好？） | LLM Q&A，不动槽位 | 否 |
| `planning_intent` | 表达出行意愿（想去大理玩） | 提取槽位、合并、追问缺失项 | 否（除非槽满） |
| `planning_ready` | 槽位已齐 | 回复确认 + 返回 `plan_request` | **是**（前端据此调 `/api/plan`） |
| `modify_plan`（预留） | 已有行程后要求调整（改预算/加日程） | 解析增量修改 → 重新规划 | 是（V2.1 再做） |

#### 2.1.3 槽位定义

| 槽位 | 必填 | 提取策略 | 缺失时追问示例 |
|------|------|---------|--------------|
| `destination` | 是 | 城市名实体识别 | 「想去哪里玩呀？」 |
| `start_date` / `end_date` | 是 | 相对日期解析（「下周末」→具体日期）+ 绝对日期 | 「计划哪天出发，玩几天呢？」 |
| `budget` | 是 | 数字 + 单位（隐含两人合计） | 「两人合计预算大概多少？」 |
| `origin` | 否 | 城市名，默认「北京」 | 不追问，默认即可 |
| `preferences` | 否 | 标签映射（浪漫/美食/自然/文化/户外…） | 可选追问「有特别偏好吗？比如浪漫、美食、户外」 |
| `pace` | 否 | 「轻松/适中/充实」关键词，默认「轻松」 | 不追问 |

**槽满判定**：`destination` + `start_date` + `end_date` + `budget` 四项齐即为 `ready`。`preferences/pace/origin` 缺失走默认值，不阻塞。

#### 2.1.4 会话状态

- MVP：后端内存字典 `sessions: dict[session_id → {slots, history, created_at}]`，配合 TTL 清理。
- V2.1：迁入 Postgres 表 `chat_sessions`（与 pgvector 同库），支持跨刷新/跨设备续聊。
- 前端 `sessionStorage` 持久化 `session_id`，保证刷新不丢会话。

#### 2.1.5 对话 Agent 编排（LangGraph 子图，可选）

对话逻辑本质是单次 LLM 结构化输出，**不一定需要** LangGraph。两种实现可选：

- **方案 A（推荐 MVP）**：纯函数 `handle_chat(session, message) → ChatReply`，一次 `call_llm` 带 structured output。简单、快、易测。
- **方案 B（演进）**：当 `modify_plan`、多轮校验、工具调用（查天气答疑）加入后，再用 LangGraph 子图编排。届时对话子图与规划图通过 condition edge 串联：对话子图 `ready` → 规划图入口。

#### 2.1.6 数据流

```
用户输入「想去大理，预算5千」
   │
   ▼
POST /api/chat { session_id, message }
   │
   ▼  一次 LLM（structured output）
{ intent:"planning_intent",
  slots:{ destination:"大理", budget:5000, start_date:null, end_date:null },
  reply:"大理很浪漫呀～打算哪天出发，玩几天？",
  ready:false }
   │
   ▼ 前端渲染 assistant 气泡
用户「下周五到周日」
   │
   ▼
POST /api/chat → 槽位合并 → intent:"planning_ready"
   reply:"好的，这就为你规划大理3天浪漫之旅～"
   ready:true, plan_request:{...完整 TripPlanRequest}
   │
   ▼ 前端检测 ready=true，切换到规划模式
POST /api/plan (SSE)  ← 既有管线零改动
   │
   ▼ partial/step/budget_alert/... 事件
PlanResult 内联渲染
```

### 2.2 pgvector 景点知识库（M10）

#### 2.2.1 为什么用向量库

高德 Amap 返回的 POI 只有名字/类型/评分/地址，**缺乏语义化描述**，对「情侣/浪漫/纪念日」这类软需求匹配弱。pgvector 存储精选/LLM 增强的 POI（带丰富描述文本），按用户偏好语义召回，与实时 Amap 结果融合，提升推荐参考性。

#### 2.2.2 数据库设计

新增 `db` 服务到 docker-compose，镜像 `pgvector/pgvector:pg16`。

表结构：

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS pois (
  id          BIGSERIAL PRIMARY KEY,
  city        TEXT NOT NULL,
  name        TEXT NOT NULL,
  type        TEXT,                 -- 自然/文化/网红/户外/人文/景点
  category    TEXT,                 -- 对应 _simplify_type 归类
  indoor      BOOLEAN DEFAULT FALSE,
  avg_cost    REAL DEFAULT 0,
  rating      REAL DEFAULT 0,
  couple_score REAL DEFAULT 7.0,
  lat         DOUBLE PRECISION,
  lng         DOUBLE PRECISION,
  description TEXT,                 -- LLM 增强的浪漫向描述
  source      TEXT DEFAULT 'curated', -- curated / amap_enriched
  embedding   vector(1536),
  updated_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS pois_city_idx ON pois(city);
CREATE INDEX IF NOT EXISTS pois_embedding_idx
  ON pois USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

Embedding 模型：`text-embedding-3-small`（1536 维，复用现有 `OPENAI_API_KEY`，成本低）。向量检索使用余弦距离 `embedding <=> :query_vec`。

#### 2.2.3 `search_poi` 双源融合算法

```
1. Amap 实时：poi_search_tool.invoke() → 12 条（既有逻辑）
2. pgvector 语义：embed(preference_text) → 检索同 city top 8
3. 去重：按 name 归一化（去空格/小写）合并
4. 重排：score = couple_score + 0.3 * (1 - cosine_distance)
5. 标记 source 字段（供 UI 展示「精选」徽章，可选）
6. 截断 top 12 返回
```

pgvector 不可用时（DB 未起/超时）降级为仅 Amap，追加 `warnings`（复用 P2 软失败机制）。

#### 2.2.4 知识库播种

新增 `backend/scripts/seed_pois.py`：
- 输入：城市列表（大理/三亚/杭州/成都/厦门…）或手工 JSON/CSV
- 流程：调 Amap 取候选 → LLM 为每条生成「情侣向 80 字描述」+ couple_score → embedding → upsert
- 幂等：按 (city, name) 唯一约束 `ON CONFLICT DO UPDATE`
- 支持手工 curated 条目覆盖（用户可维护一份 `data/curated_pois.json` 注入）

---

## 3. 里程碑拆解

### M8：对话后端 — 意图识别与槽位填充

**目标**：新增 `POST /api/chat`，单轮对话产出 intent + slots + reply，槽满时返回 `plan_request`。

**产出文件**：
- `backend/schemas/chat.py` — `ChatRequest` / `ChatReply` / `Slots` Pydantic 模型
- `backend/agents/conversation.py` — `handle_chat()` 核心逻辑（LLM structured output + 槽位合并 + ready 判定）
- `backend/services/session_store.py` — 内存会话存储（dict + TTL），V2.1 迁 Postgres
- `backend/prompts/chat_intent_prompt.md` — 意图识别 + 槽位提取 + 回复生成 prompt
- `backend/main.py` — 注册 `/api/chat` 路由
- `backend/tests/test_chat.py` — 意图分类/槽位合并/ready 触发/降级单测
- `backend/requirements.txt` — 无新依赖（复用 langchain/openai）

**验收标准**：
- `POST /api/chat` 单轮返回有效 `ChatReply` JSON
- 闲聊（「你好」）→ `intent:"greeting"`，不改动 slots
- 部分信息（「想去大理」）→ 提取 destination，追问日期
- 槽满 → `intent:"planning_ready"`，`plan_request` 可直接喂给 `/api/plan` 跑通
- 无 API key 时走 mock fallback（复用 `call_llm` 机制），不阻塞测试
- 既有 `/api/plan` 与全部 183 测试零回归

### M9：对话式前端 — Chat UI

**目标**：新增对话主界面，替代/并行于既有 `TripForm`，支持气泡对话 + 内联规划进度渲染。

**产出文件**：
- `frontend/src/pages/Chat.tsx` — 对话主页面
- `frontend/src/components/Chat/ChatWindow.tsx` — 消息列表（用户/assistant 气泡）
- `frontend/src/components/Chat/ChatInput.tsx` — 输入框 + 发送
- `frontend/src/components/Chat/SlotPanel.tsx` — 侧边已收集槽位可视化（destination/dates/budget 卡片）
- `frontend/src/services/chat.ts` — `postChat()` 封装 `/api/chat`
- `frontend/src/stores/chatStore.ts` — 对话状态（messages/slots/session_id/status）
- `frontend/src/types/chat.ts` — `ChatMessage`/`ChatReply`/`Slots` 类型
- 路由调整：`App.tsx` 默认 `/` → Chat，`/form` 保留旧表单（兼容 + E2E）
- `tripStore` 复用：chatStore 检测 `ready=true` 后调用 `tripStore.beginPlanning()`（传入 `plan_request`）

**验收标准**：
- 用户可全程用自然语言完成需求表达，无需触碰表单
- assistant 追问清晰、语气温暖（复用情侣向文案风格）
- 槽满后无缝切换到既有 Loading → PlanResult 流程（SSE 复用）
- 刷新页面会话不丢（sessionStorage 持久化 session_id）
- 既有 `/form` 路径与 Playwright E2E 不破坏
- TypeScript 检查 + Vite 构建 + 移动端响应式通过

### M10：pgvector 景点向量库

**目标**：接入 pgvector，`search_poi` 双源融合，新增播种脚本。

**产出文件**：
- `backend/services/vector_store.py` — pgvector 连接 + `query_pois(city, pref_vec, k)` + `upsert_pois()`
- `backend/services/embedding.py` — `embed_text() → list[float]`（OpenAI embedding，带缓存）
- `backend/scripts/seed_pois.py` — 知识库播种（Amap + LLM 增强 → upsert）
- `backend/data/curated_pois.json` — 手工精选 POI 种子（可选）
- `backend/agents/nodes/search_poi.py` — 改造为双源融合
- `backend/config/settings.py` — 新增 `pg_dsn`、`embedding_model`、`embedding_api_key`
- `docker-compose.yml` — 新增 `db` 服务（pgvector/pgvector:pg16）+ backend `depends_on`
- `backend/requirements.txt` — `psycopg[binary]>=3.1`、`pgvector>=0.3`
- `backend/tests/test_vector_store.py` — 查询/去重/降级单测（用 testcontainers 或 mock）
- `.env.example` — 补 `PG_DSN`、`EMBEDDING_MODEL`

**验收标准**：
- `docker-compose up` 启动 db + backend + frontend 全栈
- `python scripts/seed_pois.py --city 大理` 可完成播种且幂等
- `search_poi` 同时返回 Amap + pgvector 来源，按融合算法重排
- pgvector 故障时降级为仅 Amap，`warnings` 记录，管线不中断
- 既有 `test_nodes_core.py` 等测试在无 DB 环境下仍通过（降级路径）
- 新增双源融合测试覆盖去重与重排逻辑

**里程碑依赖**：

```
M8（对话后端）──→ M9（对话前端）
                     │
M10（pgvector）──────┘（独立，可与 M8/M9 并行，最终在 search_poi 合流）
```

---

## 4. 风险与权衡

| 风险 | 影响 | 缓解 |
|------|------|------|
| 意图识别 LLM 延迟（每轮 1–2s） | 对话体验略卡 | 用小模型（gpt-4o-mini / deepseek）/ 结构化输出约束 token；前端显示「正在思考…」 |
| 槽位误提取（日期解析错、预算单位歧义） | 规划入参错误 | 槽位在 `reply` 中复述给用户确认；`planning_ready` 前可加一轮「确认出发」 |
| pgvector 播种质量依赖 LLM 描述 | 推荐不准 | 人工 curated 覆盖优先；couple_score 保留 Amap 评分兜底；可迭代重新播种 |
| Embedding API 成本（播种期） | 一次性开销 | 仅对精选城市播种；embedding 结果可缓存复用 |
| 会话内存存储进程重启丢失 | 对话断 | MVP 可接受；V2.1 迁 Postgres；前端 sessionStorage 兜底 session_id |
| 双源 POI 去重漏判（同名异址） | 重复推荐 | 按 name 归一化 + 经纬度近邻二次去重（距离 <100m 视为同点） |

---

## 5. 额外建议（作者补充）

1. **对话记忆持久化（V2.1）**：M8 占位已留，迁 Postgres `chat_sessions` 表后支持跨设备/跨刷新续聊，并可为后续「历史行程复盘」铺路。

2. **天气/POI 答疑复用对话通道**：`question` 意图可挂 LangChain Tool（复用既有 `weather_tool`/`poi_search_tool`）做 RAG 式答疑，让 Agent 在不触发规划时也能回答「大理这周下雨吗」，提升对话价值。M8 后追加。

3. **`modify_plan` 增量调整（V2.1）**：规划完成后用户说「预算加到 8 千」「再加一天」，解析为对 `plan_request` 的 patch → 重跑管线。比从零重填表单体验好得多。

4. **pgvector 同样适配 `search_food`（M10+）**：餐厅也可建向量库（情侣餐厅精选描述），双源融合逻辑与 POI 对称，可作为 M10 的自然延伸。

5. **Embedding 本地化（成本优化）**：播种量大时可用本地 BGE/Qwen-embedding 替代 OpenAI embedding，降低成本；`embedding.py` 抽象 provider，留切换口。

6. **对话式 onboarding 引导**：首次进入 Chat 页时 assistant 主动发首条（「嗨，想去哪里过两个人的周末？」），降低空对话冷启动，符合情侣向温暖语气。

7. **槽位可视化与可编辑**：`SlotPanel` 不只展示，允许用户直接点击卡片改某一项（「其实预算改 6 千」），改完即重置 `ready`，避免全靠打字。

---

## 6. 建议实施顺序

1. **M8 对话后端**（先行，可 curl 验证，不碰前端）
2. **M10 pgvector**（与 M9 并行，独立于对话层，后端纯增量）
3. **M9 对话前端**（接 M8 接口 + 复用 M10 的更准 POI）
4. V2.1 收尾：会话持久化、modify_plan、food 向量库

每个里程碑结束保持「后端测试全绿 + 前端构建通过 + 既有 E2E 不回归」的硬门槛。
