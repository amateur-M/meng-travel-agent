## 项目：情侣旅游规划 Agent（CoupleTrip）

**一句话描述**：AI 驱动的旅游规划助手，根据日期、出发地、目的地、天气、景点、美食、预算与偏好，自动生成可执行的情侣行程。

**技术栈**：React 18 + TypeScript + Tailwind CSS + Framer Motion | Python 3.13 + FastAPI + LangChain + LangGraph | OpenAI GPT-4o

**当前阶段**：M2 进行中（Tools + Prompt 模板已完成，待接入真实 API 和 LLM）。

**下一步行动**：
1. 将 4 个 Tool 接入现有 Node（fetch_weather → weather_tool, search_poi → poi_search_tool 等）
2. 集成 OpenAI GPT-4o 替换 mock LLM 调用
3. 集成 OpenWeatherMap / 高德地图真实 API
4. 编写工具层和 prompt 模板的单元测试

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

## M2 进度摘要 (2026-08-11)

| 组件 | 状态 | 说明 |
|------|------|------|
| `tools/weather_tool.py` | ✅ | OpenWeatherMap async + 12 城市 mock fallback |
| `tools/poi_search_tool.py` | ✅ | 5 城市 × ~50 景点，偏好标签过滤，couple_score |
| `tools/food_search_tool.py` | ✅ | 5 城市 × ~25 餐厅，菜系/预算筛选，atmosphere 标签 |
| `tools/maps_tool.py` | ✅ | Haversine + nearest-neighbor，多交通方式预估 |
| `prompts/parse_input_prompt.md` | ✅ | 结构化参数提取 + 字段约束 |
| `prompts/plan_itinerary_prompt.md` | ✅ | 核心编排 + JSON Schema + 情侣向节奏 |
| `prompts/couple_copy_prompt.md` | ✅ | 按活动类型差异化语气 + 8-25 字限制 |
| `prompts/weather_adapt_prompt.md` | ✅ | 4 条调整规则 + swaps/time_shifts/warnings |
| `prompts/budget_downgrade_prompt.md` | ✅ | 4 级降级策略 + impact 分级 |
| Node 接入 Tools | ❌ | 待将 mock 数据源替换为 Tool 调用 |
| OpenAI GPT-4o 集成 | ❌ | 待接入真实 LLM |
| 真实 API 集成 | ❌ | 待配置 API Key 并启用 |
| 工具层测试 | ❌ | 待编写 test_tools.py |

---

## 外部依赖与密钥

| 服务 | 用途 | 所需密钥 |
|------|------|----------|
| OpenAI GPT-4o | LLM 推理（行程生成、寄语生成） | `OPENAI_API_KEY` |
| 和风天气 / OpenWeatherMap | 天气预报 | `WEATHER_API_KEY` |
| 高德地图 / Google Maps | POI 搜索、地理编码 | `MAP_API_KEY` |

密钥统一管理在 `backend/.env`（不提交），模板见 `.env.example`。
