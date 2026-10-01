---
name: coupletrip-backend-issues-and-fix-plan
description: meng-travel-agent/backend 代码审查问题清单与分阶段修复计划(基线 commit 0710d9f, 2026-10-01),含每项位置/根因/修复方案/验收标准
metadata:
  type: project
---

# CoupleTrip 后端问题清单与修复计划

> **状态: 已完成 (2026-10-01)。** Phase 0 / 1 / 2 全部落地 (P1–P10 + 整洁度 + `request_timeout`)。测试从基线 155 passed / 2 failed / 1 skipped → **148 passed / 0 failed / 1 skipped**(净减少来自删除死代码相关测试)。无 API key 端到端冒烟验证通过。详见 `PROGRESS.md` 的 "Backend Code-Review Fixes (2026-10-01)" 与 `KEY_DECISIONS.md` #19–#23。
>
> **剩余低优先级项(未处理,待确认)**: `_rating`/`_couple_score` 在 poi/food tool 的部分重复;QWeather/OWM 的 async+sync 双份实现收敛;CORS 配置化 + `/api/plan` 鉴权/限流;`pyproject.toml` 与 `requirements.txt` 依赖双轨合并。

- **审查基线**: commit `0710d9f`(feat: use live Amap data for POI, food, and routes),2026-10-01
- **工程路径**: `D:\Projects\myself-projects\meng-travel-agent\backend`(FastAPI + LangGraph,多 LLM provider + 高德 + 和风天气)
- **测试基线**: 155 passed / 2 failed / 1 skipped(失败原因见 P9;skip 为有意的真实 API 测试,由 `QWX_TEST_REAL_API` 环境变量控制)
- **架构速览**: `main.py`(SSE 流)→ `agents/graph.py`(9 节点 StateGraph,parse_input 三路并行取数 → plan → budget → adapt → couple_touch → output)→ `tools/`(@tool)→ `services/`(amap/llm/qweather_auth)→ `config/settings.py`。全链路有 mock 降级,无 API key 也能跑通。

---

## 一、问题清单(按严重度)

### P1 [高] /api/plan 把整张图跑两遍,LLM 成本与耗时 ×2
- **位置**: `main.py:47`(`graph.astream`)+ `main.py:64`(`graph.ainvoke`);同步回退分支同样双跑(`main.py:72-78` 中 `stream()` 之后再 `invoke()`)
- **根因**: `astream(stream_mode="values")` 已完整执行图,最后又用 `ainvoke` 重新执行一遍只为取终态。每个 value chunk 就是该超步后的全量状态,**最后一个 chunk 即终态**。
- **修复**: 在循环中记录 `final_state = chunk`,循环结束后从它取 `final_itinerary`;删除 `ainvoke`。同步回退分支只保留 `stream()`,最后一个 event 即终态。
- **验收**: 单次请求的 LLM 调用次数减半;`complete` 事件仍含完整行程;现有测试全绿。

### P2 [高] 可恢复的搜索失败被当成致命错误,直接掐断 SSE
- **位置**: `agents/nodes/search_poi.py:24-26`、`search_food.py:24-26`(异常写入 `state["error"]`);`main.py:51-53`(`error` 非空即发 `error` 事件并 return)
- **根因**: 图本身有降级能力(候选为空仍可出稿),但入口层把任何 `error` 都视为终止信号。高德 key 未配置/网络抖动时,整条请求在第一个超步后终止。且 `error` 写入后无人清理,会残留到后续阶段。
- **修复**: `AgentState` 增加 `warnings: list`(软失败累积,不阻断);search_poi/search_food 失败时 append warning 而非写 `error`;`main.py` 仅在真正致命错误时终止,`complete` 事件附带 warnings 供前端提示"部分数据来自降级"。
- **验收**: 删除高德 key 后请求仍能返回完整行程 + warning 信息,不再断流。

### P3 [高] OpenWeatherMap 解析使用上一轮循环残留变量
- **位置**: `tools/weather_tool.py:144`(`_fetch_openweathermap` 异步版,`precip = entry.get("pop", 0.0)`)
- **根因**: `entry` 是上一个 for 循环结束后残留的最后一个元素,不是当前天的数据,所有天拿到同一个 pop 值。同步版(`weather_tool.py:428`)无此问题。
- **修复**: 在按天聚合循环内正确取当天的 pop(聚合 `by_day` 时一并收集 `pop` 取 max),或直接删除该备用路径中未使用的 pop。
- **验收**: OWM 路径单测覆盖多天不同 pop。

### P4 [中] 日期解析失败后仍把非法字符串传给天气工具
- **位置**: `agents/nodes/fetch_weather.py:29-35`
- **根因**: except 分支算出 `sd = dt.today()` 但没有回写 `start_str`,仍把原始非法值传给 `weather_tool_sync`。
- **修复**: except 分支中 `start_str = sd.isoformat()` 后再计算 `end_str`。
- **验收**: 传入非法日期时天气查询不抛异常(走 mock 兜底)。

### P5 [中] 异常处理过窄导致 SSE 静默断流
- **位置**: `main.py:68`(只 `except AttributeError`)
- **根因**: 该 except 本是为兼容老版 LangGraph 的同异步回退,但节点内其他异常(如 `KeyError`)会直接抛出生成器,客户端看到连接中断而非 `error` 事件,且无日志。
- **修复**: 捕获 `Exception`,emit SSE `error` 事件,并 `logger.exception(...)` 记录堆栈;`AttributeError` 分支保留原回退逻辑。
- **验收**: 人为在节点抛异常时,客户端收到 `error` 事件而非连接中断。

### P6 [中] 预算重试回路是不可达死代码
- **位置**: `agents/graph.py:45-60`(`_route_after_budget` 要求 `over AND retries<2 AND not downgrade_applied`);`agents/nodes/budget_check.py:289-293`(超预算时必置 `downgrade_applied=True` 且 `retry_count=max(2,…)`)
- **根因**: M4 改为"budget_check 原地确定性降级"后,路由永远走 `adapt_weather`,回到 `plan_itinerary` 的分支不可达。遗留物:conditional edge、`retry_count` 机制、`BUDGET_CHECK_PROMPT`(budget_check.py:12 import 但未用)。
- **修复**: 明确二选一——(a) 接受现状,删除 conditional edge 与 retry_count,简化为直连;(b) 恢复 LLM 重规划回路(降级失败且 retries<2 时回 plan_itinerary)。建议 (a),与 M4 语义一致。
- **验收**: 图拓扑与实际行为一致,删除后测试全绿。

### P7 [中] 逐活动串行 LLM 调用,寄语生成延迟爆炸
- **位置**: `agents/nodes/add_couple_touch.py:135`(每个活动单独 `call_llm` 一次)
- **根因**: 3 天 × 6 活动 = 18 次串行调用;叠加 P1 双跑 = 36+ 次,单请求可能数分钟。
- **修复**: 改为每次调用批量生成(推荐:整个行程一次调用,prompt 附活动清单,要求返回 JSON 数组按活动名对应寄语;失败整体回退模板库)。修复 P1 后此项收益才完整。
- **验收**: LLM 调用次数从 O(活动数) 降为 O(1);寄语仍逐活动落到 `couple_note`。

### P8 [中] Pydantic 响应模型与实际产物字段不一致,且未启用校验
- **位置**: `schemas/__init__.py:57`(`Activity.activity_type` vs 节点产物用 `type`);`main.py:66`(直接 `json.dumps` 原始 dict,`TripPlanResponse` 从未参与校验)
- **根因**: schema 层对响应是"装饰品",字段漂移只会静默传到前端。前端当前实际消费的是节点产出的 `type` 字段。
- **修复**: 先确认前端契约;以现状为准将 `Activity` 字段改名/加 alias 对齐 `type`,然后 `complete` 事件前用 `TripPlanResponse.model_validate(...).model_dump(mode="json")` 做出口校验,漂移即报错。
- **验收**: 故意改坏一个节点字段名时,`complete` 前能捕获并报错;正常路径输出不变。

### P9 [中] 2 个 cassette 测试依赖个人 .env,新环境必失败
- **位置**: `tests/test_qweather_cassettes.py:22-31` + `tests/cassettes/*.yaml`
- **根因**: cassette 录制时的 QWeather host 是开发者个人域名 `kb3fc38v6c.re.qweatherapi.com`,而 `settings.qweather_base_url` 默认 `devapi.qweather.com`;测试未固定 base_url,host matcher 不匹配 → `CannotOverwriteExistingCassetteException`。只有配过 `.env` 的机器能通过。
- **修复**: 测试 fixture 中 `monkeypatch.setattr(settings, "qweather_base_url", <cassette 中的 host>)`,或用干净 host 重新录制 cassette。
- **验收**: 无 `.env` 的全新环境跑 `pytest` 全绿。

### P10 [中] 全项目零日志 + 大量静默降级
- **位置**: `tools/weather_tool.py:458-459`、`477-478` 等 `except Exception: pass`;全工程无 `logging` 调用
- **根因**: 线上无法区分"真实数据"和"mock 兜底"(mock 里有 `source: "mock"` 字段但没有透出),排障只能靠猜。
- **修复**: 引入 `logging.getLogger("coupletrip")`;静默 except 改为 `logger.warning(..., exc_info=True)`;`complete` 事件附带数据来源标记(如 `weather_source`)或统一 `degraded` 标志。
- **验收**: 模拟天气 API 失败时,日志可见 warning,响应可见降级标记。

---

## 二、整洁度与上线前检查项(低优先级)

- **重复代码**: `_fill_prompt` 在 budget_check.py:205 / adapt_weather.py:16 / add_couple_touch.py:15 三处逐字重复;`_rating`/`_couple_score` 在 poi/food 两个 tool 重复;QWeather/OWM 的 async+sync 双份实现可收敛。
- **死代码**: `_parse_qweather_daily`(weather_tool.py:161,旧 v7 格式,仅测试引用);`ITINERARY_PROMPT`/`COUPLE_MESSAGE_PROMPT`/`WEATHER_ADAPT`/`PARSE_INPUT_PROMPT`(仅测试引用);`BUDGET_CHECK_PROMPT`(被 import 未使用,随 P6 一并处理)。
- **依赖双轨**: `pyproject.toml` 与 `requirements.txt` 并存需人工同步;dev 依赖建议 `pip install -e ".[dev]"` 安装。
- **上线前**: CORS 硬编码 `localhost:5173`(main.py:22-27)需配置化;`/api/plan` 无鉴权/限流;LLM 客户端未设 `request_timeout`(services/llm.py:75-80,上游卡住会拖死请求)。
- **已知边界**: 行程 >10 天时超出 QWeather 预报窗口,`_forecast_days`(weather_tool.py:288-296)从今天起算,窗口外静默退化 mock,用户无感知——随 P10 的降级标记一起透出。

---

## 三、分阶段修复计划

### Phase 0 — 立即修(预计 0.5 天,收益最大)
| 项 | 内容 |
|---|---|
| P1 | 去掉二次执行,复用 astream 终态 |
| P5 | 兜底异常 → SSE error + 日志 |

**验收**: 单请求 LLM 调用减半;节点异常不再断流;`pytest` 全绿。

### Phase 1 — 本轮迭代(预计 1-2 天)
| 项 | 内容 |
|---|---|
| P2 | warnings 分级,搜索失败降级不阻断 |
| P3 | OWM 残留变量修正 |
| P4 | 日期回写修正 |
| P7 | 寄语批量生成(单次 LLM 调用) |
| P9 | 测试固定 qweather_base_url,消除环境耦合 |

**验收**: 无任何 API key 的环境下 `pytest` 全绿 + `/api/plan` 仍能返回完整降级行程。

### Phase 2 — 架构整理(预计 0.5-1 天)
| 项 | 内容 |
|---|---|
| P8 | 启用 TripPlanResponse 出口校验(先对齐字段) |
| P10 | 引入 logging,消除静默 except |
| P6 | 移除不可达重试回路及遗留 prompt |
| 整洁度 | 去重 `_fill_prompt`/评分函数,删死代码,合并依赖定义 |

**验收**: `pytest` 全绿;人为注入字段漂移能被出口校验捕获。

### 验证方式
```bash
cd backend
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest -q
```

## 四、修复时序建议
P1 → P5 → P9(先让测试在干净环境全绿,为后续改动建立安全网)→ P2/P3/P4/P7 → P6/P8/P10/整洁度。P7 依赖 P1 先落地,否则双跑会抵消批量化收益。
