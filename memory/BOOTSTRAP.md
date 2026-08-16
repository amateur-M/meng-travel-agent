## 项目：情侣旅游规划 Agent（CoupleTrip）

**一句话描述**：AI 驱动的旅游规划助手，根据日期、出发地、目的地、天气、景点、美食、预算与偏好，自动生成可执行的情侣行程。

**技术栈**：React 18 + TypeScript + Tailwind CSS + Framer Motion | Python 3.13 + FastAPI + LangChain + LangGraph | OpenAI GPT-4o / DeepSeek / Qwen / Kimi

**当前阶段**：M2 完成，QWeather 真实 API 已验证（JWT 自动签名 / API Key / 直传 JWT），测试 148 passed + 1 skipped；真实 QWeather 冒烟测试 1 passed。

**下一步行动**：
1. 启动 M3：前端基础 UI（TripForm + ItineraryCard）
2. 完成前后端联调后进入 M4（预算透明与天气自适应）

---

## 关键文件索引

| 文件 | 用途 |
|------|------|
| [ROADMAP.md](D:/Project/meng-travel-agent/memory/ROADMAP.md) | 实现路线图（8 个里程碑 + 验收标准 + 依赖关系） |
| [ARCHITECTURE.md](D:/Project/meng-travel-agent/memory/ARCHITECTURE.md) | 系统架构（LangGraph 设计、API 协议、数据流、目录结构） |
| [PROGRESS.md](D:/Project/meng-travel-agent/memory/PROGRESS.md) | 开发进度（里程碑完成清单） |
| [PROJECT_STRUCTURE.md](D:/Project/meng-travel-agent/memory/PROJECT_STRUCTURE.md) | 实际目录结构 + M2 新增文件清单 |

---

## 恢复上下文步骤

新会话开始时，按顺序阅读以下文件即可完全恢复项目上下文：

1. 先读本文件（`memory/BOOTSTRAP.md`）—— 了解项目是什么、处于什么阶段
2. 再读 `memory/ROADMAP.md` —— 了解当前里程碑、已完成工作、下一步任务
3. 最后读 `memory/ARCHITECTURE.md` —— 了解技术决策、Agent 设计、API 协议
4. 如有需要，检查 `frontend/` 和 `backend/` 的实际代码确认当前进度

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
