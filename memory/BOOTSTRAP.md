## 项目：情侣旅游规划 Agent（CoupleTrip）

**一句话描述**：AI 驱动的旅游规划助手，根据日期、出发地、目的地、天气、景点、美食、预算与偏好，自动生成可执行的情侣行程。

**技术栈**：React 18 + TypeScript + Tailwind CSS + Framer Motion | Python 3.13 + FastAPI + LangChain + LangGraph | OpenAI GPT-4o / DeepSeek / Qwen / Kimi

**当前阶段**：M0–M7 全部交付，**V2（P0–P3）与 V3（对话记忆与持久化）均已完成**。后端测试 **422 passed + 1 skipped**，前端 `tsc -b` + `vite build` 通过、`npm run check:store` 49/49。

**V3 升级摘要**（详见 [UPGRADE_V3_CONVERSATION_MEMORY.md](UPGRADE_V3_CONVERSATION_MEMORY.md)）：
起因是"对话记忆没有做"：`get_history()` 零调用点（历史写了从不读）、`question` 意图回固定话术、前端只存 `session_id`。进一步发现 **PostgreSQL 认证失败 + Redis 不支持 RESP3 `HELLO`，两个持久化后端全程静默降级** —— 连已有的槽位记忆与行程持久化都从未真正生效。已完成：
- **L0 短期记忆 + 真对话**：会话/消息迁 PostgreSQL（`ConversationStore`）；`acall_llm(history=...)` 真正把多轮上下文送进 prompt；`question`/`greeting` 走 `acall_llm_text()` 真回答，规划类用确定性模板省一次调用；**先落 user 消息再调模型**、`message_id` 幂等
- **L1/L2/L3 长期记忆**：会话内滚动摘要（带覆盖游标，增量压缩）+ 跨会话画像（只增不删，冲突保留旧值）+ 情节召回（历史行程与 `plan_feedback`，反馈表首次进入在线链路）。**全部结构化存储 + SQL 召回，无 embedding**
- **持久化与恢复**：活动会话存 sessionStorage（多标签隔离）、localStorage 存恢复种子/缓存/`client_id`；刷新水合完整记录；404 → 新建；末尾无回复 → "重新生成"；会话列表可新建/切换/重命名/删除；会话↔行程互相关联
- **可观测性**：`/health` 暴露各存储真实状态与失败原因（原只报 `PoolTimeout`，掩盖了认证失败）；启动 ERROR 告警；连接失败超时 30s→5s
- **移除 Redis**：会话迁 PG 后 Redis 零消费者（限流器本就未用），依赖/compose/env 均已清理

**下一步行动**：
1. 只剩**浏览器专属**的手工确认（服务端行为已全部自动化）：真实标签页刷新后的水合、
   两个标签页并发写同一会话、关标签页重开、跨天回来 —— 见 [DEPLOY.md](DEPLOY.md) §五
2. OpenTelemetry tracing（V2 唯一跳过项）——LLM 与 Amap/QWeather 调用暂无 span
3. 如需扩展：多用户协作编辑、更多目的地、离线缓存等

**环境提醒**：
- `backend/.venv` 需与 `requirements.txt` 保持同步（`pip install -r requirements.txt`）；曾因缺少 V2 依赖导致 pytest 直接 16 个 collection error
- PostgreSQL 已初始化并在用（密码是用户自定义的，写在 gitignored 的 `backend/.env`）；
  连不上时应用**不会崩**，只是不持久化，`/health` 会显示 `degraded` 且带原因
- **测试不会碰你的开发库**：`tests/conftest.py` 有 autouse 隔离夹具，
  需要真实库的测试用 `@pytest.mark.real_database` 显式退出隔离
- **`OFFLINE_MODE=true`** 可清空全部外部凭据，让冒烟/演示零成本离线运行。
  不要用"把 key 设成空字符串"的办法 —— **空环境变量不会覆盖 `.env`**
  （pydantic-settings 视为未设置），曾因此意外发出真实付费请求
- 存储层用**同步 psycopg 池 + `asyncio.to_thread`**：psycopg 异步模式在 Windows 默认 `ProactorEventLoop` 上会直接报错，不要改回 `AsyncConnectionPool`
- **本机 shell 是 Windows PowerShell 5.1**（桌面版，默认代码页 `gb2312`），不是 pwsh 7：
  `Get-Content` / `Set-Content` 默认按 GBK 读写，**不要用它们往返 UTF-8 文本文件**
  （会把中文/框线字符二次编码、并写入 BOM —— 已因此损坏过 4 个 memory 文档和 2 个测试文件，
  均用 `git checkout` 或编辑工具恢复）。改文本请用编辑工具
- 本机未安装 Docker，但 PostgreSQL 18.6（`D:\Software\Postgresql18`）为原生安装

---

## 关键文件索引

| 文件 | 用途 |
|------|------|
| [ROADMAP.md](ROADMAP.md) | 实现路线图（8 个里程碑 + 验收标准 + 依赖关系） |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 系统架构（LangGraph 设计、记忆分层、API 协议、数据模型） |
| [PROGRESS.md](PROGRESS.md) | 开发进度（里程碑 + V2/V3 完成清单） |
| [GOALS.md](GOALS.md) | 当前迭代目标与验证记录 |
| [UPGRADE_V2_AUDIT.md](UPGRADE_V2_AUDIT.md) | V2 技术债诊断与优先级重排理由 |
| [UPGRADE_V2_EXECUTION_PLAN.md](UPGRADE_V2_EXECUTION_PLAN.md) | V2 可跟踪执行计划（任务 ID + 状态） |
| [UPGRADE_V3_CONVERSATION_MEMORY.md](UPGRADE_V3_CONVERSATION_MEMORY.md) | V3 对话记忆设计 + P0–P4 任务表 + §11 设计修正与未闭环项 |
| [DEPLOY.md](DEPLOY.md) | 部署文档（本地 / Docker / E2E / CI / 手工冒烟清单） |
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | 实际目录结构 + 新增文件清单 |

---

## 恢复上下文步骤

新会话开始时，按顺序阅读以下文件即可完全恢复项目上下文：

1. 先读本文件（memory/BOOTSTRAP.md）—— 了解项目是什么、处于什么阶段
2. 再读 memory/ROADMAP.md —— 了解当前里程碑、已完成工作、下一步任务
3. 再读 memory/UPGRADE_V2_AUDIT.md —— 了解 V2 升级的 6 项技术债诊断与 P0-P3 优先级重排理由
4. 再读 memory/UPGRADE_V2_EXECUTION_PLAN.md —— 了解 V2 可跟踪执行计划（任务带 ID+状态）
5. 再读 memory/UPGRADE_V3_CONVERSATION_MEMORY.md —— 了解对话记忆分层（L0–L3）、12 场景恢复矩阵、**§11 设计修正与未闭环项**
6. 最后读 memory/ARCHITECTURE.md —— 了解技术决策、Agent 设计、记忆分层、API 协议

如有需要，检查 frontend/ 和 backend/ 的实际代码确认当前进度

当前项目状态：M0-M7 已交付，V2 P0–P3 已完成，V3 对话记忆与持久化已完成
（唯一未闭环项：本地 PostgreSQL 需以超级用户执行一次 `backend/scripts/init_local_db.sql`）。

---

## 核心差异化（决策备忘）

- **情侣向**：浪漫节奏（不赶场、留白时间）、共情文案（每节点一句情侣寄语）
- **预算透明**：每步花费实时累计，超预算自动降级方案
- **天气自适应**：雨天自动切室内方案，高温自动避开户外时段
- **节奏控制**：上午/下午/晚间三档，每档最多 2 个活动

---

## M2 完成摘要 (2026-08-11)

| 组件 | 状态 | 说明 |
|------|------|------|
| 4 个 LangChain Tools | ✅ | weather/poi/food/maps，@tool 装饰，mock fallback |
| 5 个 Prompt .md 模板 | ✅ | parse_input/plan_itinerary/couple_copy/weather_adapt/budget_downgrade |
| Node → Tool 接入 | ✅ | fetch_weather/search_poi/search_food 全部接入 |
| LLM 服务层 | ✅ | services/llm.py — call_llm() 统一入口 + mock fallback |
| Node → LLM 接入 | ✅ | plan_itinerary/budget_check/adapt_weather/add_couple_touch 全部接入 |
| QWeather 鉴权 | ✅ | JWT 自动签名 / API Key / 直传 JWT，兼容 GeoAPI + Weather v1 |
| `plan_itinerary._build_prompt()` | ✅ | 修复模板替换并返回完整 prompt |
| 测试 | ✅ | 148 passed + 1 skipped（新增 QWeather 鉴权单测、真实 API 冒烟测试与 vcrpy cassette 测试） |
| 真实 API 验证 | ✅ | Qwen 已通过；QWeather GeoAPI 与 daily forecast 已通过，并录制 vcrpy cassette |

---

## M3 前端重构 (2026-08-18)

| 模块 | 状态 | 说明 |
|------|------|------|
| 页面 | ✅ | Home 输入 / PlanResult 时间轴展示 / Loading 规划动画 |
| 组件 | ✅ | TripForm、Timeline、TimelineCard、BudgetBar、WeatherBadge、CoupleQuote、SSEProgress |
| 状态管理 | ✅ | Zustand `tripStore`（表单/结果/预算）+ `uiStore`（主题/动画） |
| API 层 | ✅ | `api.ts` Axios + `sse.ts` SSE 连接管理 + `plan.ts` POST /api/plan 真实流式解析 |
| Mock 数据 | ✅ | `mocks/trip.ts` 保留为离线预览，正式规划已由后端真实数据取代 |
| 后端联调 | ✅ | 修复 `parse_input` 未包含结束日的天数计算，3 天请求现返回 3 天行程 |
| 视觉与动效 | ✅ | 暖粉/奶白/淡金、圆角软阴影、Framer Motion stagger、移动端优先 |
| 验证 | ✅ | TypeScript 类型检查与 Vite 生产构建通过 |

---

## M4 预算透明与天气自适应 (2026-08-31)

| 模块 | 状态 | 说明 |
|------|------|------|
| 后端预算核算 | ✅ | `budget_check` 增加 `warning_level`、`spending_ratio`、实际降级与 `downgrade_applied` |
| 后端天气调整 | ✅ | `adapt_weather` 雨天切室内、高温避正午，并记录 `weather_swaps` |
| 后端输出归一化 | ✅ | `output_format` 补充 `trip_date`、每日高低温、`daily_cost`、`weather_swaps` |
| 前端预算预警 | ✅ | 新增 `BudgetAlerts`，预算 90% 黄色提示、超预算展示降级说明 |
| 前端天气说明 | ✅ | `WeatherBadge`/`Timeline` 展示天气切换原因 |
| 真实数据接入 | ✅ | POI/美食/路线替换本地 mock，走高德 Web Service |
| 验证 | ✅ | 后端 148 passed + 1 skipped，前端构建通过 |

---

## 外部依赖与密钥

| 服务 | 用途 | 所需密钥 |
|------|------|----------|
| OpenAI GPT-4o | LLM 推理（行程生成、寄语生成） | `OPENAI_API_KEY` |
| DeepSeek | LLM 推理（可选 provider） | `DEEPSEEK_API_KEY` |
| Qwen（通义千问） | LLM 推理（可选 provider） | `QWEN_API_KEY` |
| Kimi（月之暗面） | LLM 推理（可选 provider） | `KIMI_API_KEY` |
| QWeather / 和风天气 | 天气预报 | `WEATHER_API_KEY`（PEM 私钥 / JWT / API Key） + `QWEATHER_BASE_URL` + `QWEATHER_CREDENTIAL_ID` + `QWEATHER_PROJECT_ID` |
| 高德地图 / Google Maps | POI 搜索、地理编码 | `MAP_API_KEY` |

密钥统一管理在 `backend/.env`（不提交），模板见 `.env.example`。

---

## M6 SSE 流式交互强化 (2026-10-03)

| 模块 | 状态 | 说明 |
|------|------|------|
| 后端 SSE 事件扩展 | ✅ | `stream_mode="updates"` 逐节点发射 step/partial/budget_alert/weather_swap/message/complete/error 7 类事件 |
| 后端 `_emit_node_events` | ✅ | 按节点阶段发射细粒度事件：plan_itinerary/rhythm_control → partial（逐日）、budget_check → budget_alert、adapt_weather → weather_swap（逐项）、add_couple_touch → message（逐活动） |
| 后端 fallback 清理 | ✅ | 删除过时的 `except AttributeError` sync fallback 分支（LangGraph 1.2.12 astream 可用），避免误捕获节点异常 |
| 前端 `postEventStream` 重写 | ✅ | 支持全部 7 类事件 + 断连自动重试（最多 2 次，退避 800ms×attempt） |
| 前端 `StreamingItinerary` 组件 | ✅ | 新增，partial 事件到达时逐日逐时段 progressive 渲染活动卡片 |
| 前端 `tripStore` 状态扩展 | ✅ | 新增 streamingDays/budgetAlert/weatherSwaps/coupleMessages 流式状态 + 事件回调订阅 |
| 前端 Loading 页改造 | ✅ | 进度条下方逐步渲染流式行程 + 预算/天气/寄语徽章实时计数 |
| 前端类型扩展 | ✅ | 新增 PartialEvent/BudgetAlertEvent/WeatherSwapEvent/MessageEvent 类型 |
| SSE 测试 | ✅ | 16 个新测试：helper 单测 + 流式集成（事件类型/顺序/complete 结构验证） |
| 验证 | ✅ | 后端 183 passed + 1 skipped，前端 TS 检查 + Vite 构建通过 |

