## 项目：情侣旅游规划 Agent（CoupleTrip）

**一句话描述**：AI 驱动的旅游规划助手，根据日期、出发地、目的地、天气、景点、美食、预算与偏好，自动生成可执行的情侣行程。

**技术栈**：React 18 + TypeScript + Tailwind CSS + Framer Motion | Python 3.13 + FastAPI + LangChain + LangGraph | OpenAI GPT-4o / DeepSeek / Qwen / Kimi

**当前阶段**：M7 完成，全部 8 个里程碑交付。Docker 一键部署 + Playwright E2E + CI 流水线已落地；后端测试 183 passed + 1 skipped，前端 TypeScript 类型检查通过。

**下一步行动**：
1. 项目已全部交付，可进入维护/迭代阶段
2. 如需扩展：多用户协作编辑、更多目的地、离线缓存等

---

## 关键文件索引

| 文件 | 用途 |
|------|------|
| [ROADMAP.md](D:/Project/meng-travel-agent/memory/ROADMAP.md) | 实现路线图（8 个里程碑 + 验收标准 + 依赖关系） |
| [ARCHITECTURE.md](D:/Project/meng-travel-agent/memory/ARCHITECTURE.md) | 系统架构（LangGraph 设计、API 协议、数据流、目录结构） |
| [PROGRESS.md](D:/Project/meng-travel-agent/memory/PROGRESS.md) | 开发进度（里程碑完成清单） |
| [PROJECT_STRUCTURE.md](D:/Project/meng-travel-agent/memory/PROJECT_STRUCTURE.md) | 实际目录结构 + 新增文件清单 |

---

## 恢复上下文步骤

新会话开始时，按顺序阅读以下文件即可完全恢复项目上下文：

1. 先读本文件（memory/BOOTSTRAP.md）—— 了解项目是什么、处于什么阶段
2. 再读 memory/ROADMAP.md —— 了解当前里程碑、已完成工作、下一步任务
3. 再读 memory/UPGRADE_V2_AUDIT.md —— 了解 V2 升级的 6 项技术债诊断与 P0-P3 优先级重排理由
4. 再读 memory/UPGRADE_V2_EXECUTION_PLAN.md —— 了解可跟踪执行计划（41 个任务带 ID+状态，持久化用 PostgreSQL）
5. 最后读 memory/ARCHITECTURE.md —— 了解技术决策、Agent 设计、API 协议

如有需要，检查 frontend/ 和 backend/ 的实际代码确认当前进度

当前项目状态：M0-M7 已交付，V2 升级执行中。P0.1 行程持久化已完成 ✅（PostgreSQL + REST 端点补齐 + 前端 plan_id 恢复），后端 190 passed + 1 skipped，前端 tsc+build 通过。下一步是 P0.2 LLM 异步化。执行计划中每个任务带唯一 ID 与 ⬜/🔄/✅ 状态标记，进度可在 UPGRADE_V2_EXECUTION_PLAN.md 顶部总览表查看。

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

