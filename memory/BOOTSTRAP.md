## 项目：情侣旅游规划 Agent（CoupleTrip）

**一句话描述**：AI 驱动的旅游规划助手，根据日期、出发地、目的地、天气、景点、美食、预算与偏好，自动生成可执行的情侣行程。

**技术栈**：React 18 + TypeScript + Tailwind CSS + Framer Motion | Python 3.13 + FastAPI + LangChain + LangGraph | OpenAI GPT-4o

**当前阶段**：M1 完成（Agent 引擎 + 96 个测试全部通过），准备启动 M2。

**下一步行动**：启动 M2 —— 对接外部 API（天气 + 地图 POI + OpenAI GPT-4o），替换 M1 中的 mock 数据。

---

## 关键文件索引

| 文件 | 用途 |
|------|------|
| [ROADMAP.md](D:/Project/meng-travel-agent/memory/ROADMAP.md) | 实现路线图（8 个里程碑 + 验收标准 + 依赖关系） |
| [ARCHITECTURE.md](D:/Project/meng-travel-agent/memory/ARCHITECTURE.md) | 系统架构（LangGraph 设计、API 协议、数据流、目录结构） |

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

## 外部依赖与密钥

| 服务 | 用途 | 所需密钥 |
|------|------|----------|
| OpenAI GPT-4o | LLM 推理（行程生成、寄语生成） | `OPENAI_API_KEY` |
| 和风天气 / OpenWeatherMap | 天气预报 | `WEATHER_API_KEY` |
| 高德地图 / Google Maps | POI 搜索、地理编码 | `MAP_API_KEY` |

密钥统一管理在 `backend/.env`（不提交），模板见 `.env.example`。
