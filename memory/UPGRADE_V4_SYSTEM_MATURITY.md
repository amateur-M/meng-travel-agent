# CoupleTrip V4：系统成熟度重构 — 执行结果

> 本文记录 V4 方案（`V4_系统成熟度重构`）的落地结果。起因：用户反馈"前端丑、后端整体
> 定位也不清晰，不符合一个系统的标准"。定位决策已确认：**对话式为唯一主入口**。
> 执行分 P0–P4 五阶段，每阶段硬门槛为后端 pytest 全绿 + 前端 build 通过。
> 关联文档：`ARCHITECTURE.md`（§4/§5/§6.2 已同步）、`PROGRESS.md`（V4 章节）。

---

## 0. 根因与对策对照

| 症状 | 根因 | V4 对策 | 状态 |
|------|------|---------|------|
| 定位不清晰 | 对话式与表单向导两套范式并存 | Chat(`/`) 为唯一主入口；`/form` 降级为隐藏批量录入；`/result` 作全屏详情 | ✅ |
| 后端不像系统 | `main.py` 673 行巨石，五种职责混杂，无分层 | 拆 `api/`（路由）+ `services/`（SSE/流管线/存储），`main.py` 收敛为 `create_app()`（112 行） | ✅ |
| 后端重复代码 | `_stream_graph` 与 `_run_graph_to_queue` ~50 行近乎重复 | 抽出共享 `iter_graph_events(initial_state, plan_id)`，两者都基于它 | ✅ |
| 前端乱 | Chat 页 7-8 个条件横幅竖排堆叠 | 收敛为三段（header / 消息流 / composer），状态条合一 | ✅ |
| 前端丑 | 纯文字 + 浅色卡片，无视觉主体 | POI 配图 + 主题占位插画、目的地 hero 头图、Chat 空状态插画 | ✅ |
| 深色模式失效 | 变量定义了 dark，组件全用硬编码颜色 | 颜色变量化 + `ThemeToggle` 入口（此前无 UI 入口 = 假开关） | ✅ |
| 文档与现实不符 | ARCHITECTURE 写 `backend/app/`、数据流节点名过时 | §4/§5/§2.1/§6.2 全部对齐真实结构 | ✅ |

---

## 1. P1 后端分层重构（纯结构，零行为变化）

**目标结构（已落地）**：

```
backend/
  api/
    __init__.py
    health.py       # GET /health
    chat.py         # POST /api/chat + sessions CRUD
    profile.py      # /api/profile + /api/chat/recall
    plan.py         # POST /api/plan + stream + history + get + delete + feedback
    errors.py       # 统一异常处理（RateLimitExceeded 等）
    rate_limit.py   # slowapi limiter 单例
  services/
    sse.py          # _sse / _phase_message / _emit_node_events
    plan_pipeline.py# plan_streams 总线 + iter_graph_events + run_graph_to_queue / _stream_graph
  main.py           # create_app()：日志/Instrumentator/limiter/CORS/include_router/lifespan（112 行）
```

**要点**：
- `_stream_graph`（yield 事件）与 `run_graph_to_queue`（put 到队列）此前是两份近乎重复的
  图遍历逻辑。现抽出共享异步生成器 `iter_graph_events(initial_state, plan_id)`，两者都基于它，
  重复逻辑体消除。`_stream_graph` 迁到 pipeline 模块并保留导出，`test_sse.py` 改 import 路径。
- 端点路径、请求/响应契约、`response_model` 完全不变——纯结构重构。
- 测试 patch 目标随迁移更新，区分三类拓扑：
  - **instance-attribute patch**（patch 单例对象方法，如 `plan_store.save`）：跨模块引用仍生效，
    改为 canonical 路径更稳健；
  - **whole-object rebind**（如 `conversation_store`）：必须指向实际使用它的模块（`api.chat` 与
    `api.profile` 两处都 patch）；
  - **function patch**（`handle_chat`/`load_episodic_recall`/`run_graph_to_queue`/`_stream_graph`）：
    必须指向端点查找该名字的模块。

**回归**：`python -m pytest -q` → **461 passed + 3 skipped**（方案文档写的 422+1 已过时，套件已增长）。

**环境注意**：`.venv` 由 uv 管理（无 pip）。缺依赖时用
`uv pip install --python .\.venv\Scripts\python.exe <pkg>` 安装。

**不在本阶段**：`plan_streams` 进程内存的多 worker fan-out 问题（已知限制，触发条件见
ARCHITECTURE §6.1，本轮不动）。

---

## 2. P0 产品定位收口

- **决策**：Chat(`/`) 为唯一主入口；`/result` 保留为全屏行程详情（仅从 Chat 的 `ChatPlanCard`
  "查看完整行程"进入）；`/loading` 保留为在途行程恢复中转（`resumeExistingPlan` 依赖）；
  `/form` 降级为隐藏批量录入入口（供 E2E 与高级用户，此前已不在任何主导航）。
- 抽出 `components/AppHeader.tsx` 统一页头（Home/Chat/PlanResult 共用品牌块），消除视觉分叉。
- 新增 `config/layout.ts` 的 `CONTENT_WIDTH`（`chat = max-w-2xl` / `page = max-w-6xl`）宽度令牌，
  各页按场景引用。
- App.tsx / `e2e/full_flow.spec.ts` 补意图注释。

---

## 3. P2 前端信息架构重排 + 深色模式修复

### P2.1 Chat 横幅堆叠治理
- `components/Chat/ChatStatusRegion.tsx`：把"重新生成 / 正在规划 / 出错"三条**互斥**横幅合并为
  单一状态条，按优先级 `error > planning > pending` 只渲染一个（此前失败 + 规划中会同时画两条）。
  浅色 amber/rose/blush chip 自带深色文字，两主题都可读，显式豁免深色重映射。
- `components/Chat/ChatComposer.tsx`：状态条 + 槽位面板 + 开始规划按钮 + 输入框合为一体化行动区。
- `Chat.tsx` 收敛为三段：header / 消息流（行程卡作 `ChatWindow` 的 `footer` 随滚动流，实现
  "对话 → 行程 → 继续对话"同一滚动流）/ composer。条件块从 7-8 个降到 3 段。

### P2.2 深色模式修复（真实 bug）
- **接线**：`tailwind.config.ts` 的 cream/blush/gold/ink 颜色改为 `rgb(var(--x) / <alpha-value>)`；
  `index.css` 为 `:root` 与 `:root[data-theme="dark"]` 两套 RGB 三元组赋值（light 精确匹配原 hex，
  dark 翻转：surface/cream 变深、ink 反转、blush/gold 色阶反转）。`bg-white` → `bg-surface`。
- **实心 CTA 冲突解决**：`blush-500/600` 既作实心按钮填充（配白字）又作强调文字，翻转会破坏其一。
  对策：强调文字/描边留在翻转的 blush 色阶，实心填充分离到**固定 `brand` 色**
  （`brand.DEFAULT = #cc456d` / `brand.dark = #a93255`，不随主题翻转），保证两主题下白字对比度。
  迁移：`bg-blush-500` → `bg-brand`、`bg-blush-600` → `bg-brand-dark`（ChatComposer/ChatInput/
  ChatWindow/TripForm/AppHeader/Loading）。
- 侧边栏遮罩 `bg-ink-900/30` → `bg-black/40`（避免 ink-900 在深色翻转近白使遮罩变白）。
- 新增 `components/ThemeToggle.tsx` 挂在 `AppHeader`（每页可切换）——此前 `uiStore.theme` 已通过
  `document.documentElement.dataset.theme` 接线到 CSS 变量，但**无任何 UI 调用 `setTheme`**，
  深色板不可达（假开关）。

**验收**：`tsc -b && vite build` 通过；`npm run check:store` **49/49 + 28/28**。

---

## 4. P3 视觉升级

- **POI 配图（后端）**：`schemas.Activity` 加 `image_url: Optional[str]`；`search_poi` 从 curated
  （`item["image_url"]`）与高德（`photos[0]`）提取；`output_format._image_lookup` 按活动 name 回填
  `image_url`（活动由 LLM/mock 从 POI 名生成，本身不带图，需在打包时补齐）。
- **配图渲染（前端）**：`types/trip.ts` `Activity` 加 `image_url?`；新增
  `components/TimelineCard/ActivityImage.tsx`——有图渲染 `<img loading="lazy" onError=回退>`，
  无图按活动类型渲染渐变主题占位插画（景点/美食/室内/户外/文化/冒险/留白各配色 + 图标）。
  `TimelineCard` 接入：有真实图或非留白活动展示 banner，留白无图保持轻量。
- **氛围层**：
  - `components/Chat/ChatEmptyState.tsx`：渐变插画徽章 + "你们想去哪儿？" 引导 + 3 条快速开始建议
    chip（点击直接作为首条消息发送），替换原来孤零零一个心形图标 + 一行灰字。
  - `PlanResult` 头部升级为目的地 **hero 头图**（固定 brand 渐变 + gold 光晕 + 半透明白 chip），
    深浅色下白字对比度都成立。
  - `ChatPlanCard` 加同款渐变头部条，与详情页视觉语言一致。
- **令牌收敛（T3.5）**：`index.css` `@layer components` 定义 `.ct-card` / `.ct-input` /
  `.ct-btn-primary` 三个语义类，迁移 BudgetBar / SlotPanel / Timeline / TripForm / Home /
  DateRangePicker / DestinationSelect / ChatComposer 的重复字面量（padding/size 仍留调用点作
  utility 覆盖，因 @layer components 在 utilities 之下）。
- **T3.3 静态地图：评估后跳过**。需高德 key + 联网瓦片，离线环境不可行；POI 配图已提供视觉主体，
  地图另立计划。

**验收**：后端 461 passed + 3 skipped（新增 `image_url` 字段不破坏既有测试）；前端 build 通过。

---

## 5. P4 文档同步

- `ARCHITECTURE.md` §5 目录改为**真实结构**（去 `backend/app/`、加 `api/` + `services/sse.py` +
  `plan_pipeline.py`，标注 backend 为导入根）；§4 数据流图节点名对齐实际
  （parse_input/fetch_weather/search_poi/search_food/plan_itinerary/rhythm_control/budget_check/
  adapt_weather/add_couple_touch/output_format）+ 入口改 Chat；§2.1 State 由 `TripPlanState`
  改为真实的 `agents/state.py::AgentState`；§6.2 新增 V4 决策表。
- §3.1 API 表核对已含全部端点（profile/recall/feedback/sessions），无需补。
- `PROGRESS.md` 加 V4 里程碑行 + 详细章节；`BOOTSTRAP.md` / `GOALS.md` 追加 V4 摘要。

---

## 6. 验收清单

| 项 | 命令 | 结果 |
|----|------|------|
| 后端全量回归 | `python -m pytest -q` | 461 passed + 3 skipped ✅ |
| 前端类型 + 构建 | `npm run build`（tsc -b && vite build） | 通过 ✅ |
| 前端 store 检查 | `npm run check:store` | 49/49 + 28/28 ✅ |
| Chat 条件块收敛 | 人工核对 Chat.tsx | 7-8 段 → 3 段 ✅ |
| 深色模式真实生效 | ThemeToggle 切换 + CSS 变量 | 已接线且有入口 ✅ |

**E2E**：本机无浏览器，`e2e/full_flow.spec.ts` 纳入 CI + `tsc -b` 类型检查（沿用 V3 约定）。
**离线冒烟**：`scripts/smoke_e2e.py`（OFFLINE_MODE）需运行中服务器 + 真实库，本轮未跑（无库环境）。

---

## 7. 遗留与后续

- **多 worker SSE fan-out**：`plan_streams` 仍是进程内存，多 worker 部署才需引入 broker
  （见 ARCHITECTURE §6.1 触发条件），本轮未动。
- **curated POI 配图**：`curated_pois.json` 的 `image_url` 管路已就绪，但离线未填真实图 URL
  （不臆造失效外链）；接入图床/真实资源后直接补字段即可，前端自动渲染。
- **静态地图（T3.3）**：需高德 key + 联网，另立计划。
- **OTel tracing**：V2 唯一跳过项，本轮同样未纳入。
