# V5 企业级健壮性审计与修复（2026-11-02）

> 起因：用户要求"以企业级 Agent 视角分析代码现状，重点找 bug 与逻辑问题"，随后要求"按优先级修复"。
> 本文件固化本轮**审计发现 + 已实现修复**的清单，作为可追溯的变更记录。
> 结论汇总见 `PROGRESS.md` 的 V5 章节；关键设计取舍见 `KEY_DECISIONS.md` #27–#32。

## 审计范围

覆盖对话核心（conversation/memory/llm）、API 层（chat/plan/profile/health/deps）、
服务层（plan_pipeline/sse/storage/conversation_store）、graph 节点、外部集成
（resilience/amap/qweather/rate_limit/settings）与前端（chatStore/tripStore/sse.ts/plan.ts）。
共识别 21 项问题，本轮修复其中 16 项，2 项标注为需部署/架构决策（未改代码）。

---

## P0 严重（违背承诺 / 数据泄漏 / 生产阻塞）

### P0-1 SSE「进行中」重连必然 404
- **现象**：客户端在规划进行中断线，`_live_stream` 的 `finally` 立即 `plan_streams.pop(plan_id)`；
  前端按设计重连同一 GET URL 时 `plan_streams.get()` 已为 `None` → `not_found`。
  直接违背 V2 P0.3「断线重连不重跑」承诺（只有已完成的计划走 DB 重放才成功）。
- **修复**：`backend/api/plan.py` 移除消费者断开时的 `pop`；清理权唯一归属后台任务。
- **文件**：`backend/api/plan.py`（`_live_stream`）

### P0-2 plan_streams 内存泄漏
- **现象**：POST 建 queue + 后台任务，但清理只在 `_live_stream.finally`；
  若客户端从不消费 GET 流（超时/关页/爬虫），entry 永不回收。
- **修复**：`backend/services/plan_pipeline.py` `_run_graph_to_queue` 的 `finally`
  在推完 sentinel 后统一 `plan_streams.pop(plan_id, None)`。此时结果已落库，
  重连走 DB 重放，删除内存 queue 安全；进行中的重连仍可重新挂载。
- **文件**：`backend/services/plan_pipeline.py`

### P0-3 L3 情景召回跨租户泄漏
- **现象**：`load_episodic_recall` 用 `plan_store.list(20, 0)` 取全局最新 20 条 plan，
  未按用户隔离；用户 A 的历史行程可能被召回进用户 B 的对话。
- **修复**：
  - `plans` 表新增 `client_id` 列（`CREATE TABLE` + 幂等 `ALTER TABLE ADD COLUMN IF NOT EXISTS`）+ 索引；
  - `PlanStore.save(..., client_id=)` 落归属，`PlanStore.list(..., client_id=)` 按归属过滤（`None` 保留单用户语义）；
  - `POST /api/plan` 从 `session_id` 解析 `client_id` 后落库；
  - `load_episodic_recall(client_id)` 按用户召回。活动级反馈（按 activity_name 聚合）保持全局——它是人气信号而非个人数据。
- **文件**：`backend/services/storage.py`、`backend/api/plan.py`、`backend/agents/conversation.py`

---

## P1 高（逻辑错误 / 可靠性缺陷）

### P1-4 熔断器被 tenacity 重试打穿
- **现象**：`resilient_call` 用 `retry_if_exception_type((Exception,))`，`CircuitBreakerOpen`
  也被重试；熔断打开时本应立即短路，却空跑 3 次 + 指数退避（同步线程阻塞 ~3s）。异步版反而是对的（行为不一致）。
- **修复**：改 `retry_if_not_exception_type(CircuitBreakerOpen)`；docstring 更正。
  同时给 `CircuitBreaker` 计数加 `threading.Lock`（P2-13：`resilient_call` 经 `to_thread` 并发调用有竞态）。
- **文件**：`backend/services/resilience.py`

### P1-5 regenerate 对槽位变更非幂等
- **现象**：`regenerate` 是「回复未到达、用同一 message_id 重试失败轮」（recovery #5），非重新生成。
  但 `handle_chat` 会重跑 `postprocess_patch`，而补丁是**相对**当前槽位解析的（"再加一天"→ end_date+1），
  首次已改后重试会二次叠加（+2 天）。
- **修复**：`chat_sessions` 新增 `slots_message_id` / `last_modify_patch`；
  `update_slots(..., message_id=, modify_patch=)` 记录归属轮次；
  `handle_chat` 检测同一 message_id 已拥有当前槽位时，复用已持久化槽位与补丁，跳过二次变更。
- **文件**：`backend/services/conversation_store.py`、`backend/agents/conversation.py`、`backend/tests/fake_conversation_store.py`

### P1-6 连接池一旦不可用即永久禁用
- **现象**：`_pool_unavailable` 置位后进程生命周期内不再重连（启动竞态会永久静默降级）。
- **修复**：改为 30s 冷却（`_POOL_RETRY_COOLDOWN` + `_pool_unavailable_since`），冷却后允许重试自愈。
- **文件**：`backend/services/storage.py`、`backend/services/conversation_store.py`

### P1-7 天气按位置索引取值（错位隐患）
- **现象**：`output_format._normalise_days` 与 `add_couple_touch` 用 `weather_keys[day_index]`
  按顺序取天气，而 `weather_data` 是以 ISO 日期为 key 的 dict；覆盖/顺序不一致时会张冠李戴。
- **修复**：改为按日期取值——`output_format` 用 `weather.get(trip_date)`；
  `add_couple_touch`（早于 output_format 运行、draft 无 trip_date）用 `start_date + day_index` 推导 ISO 日期。
- **文件**：`backend/agents/nodes/output_format.py`、`backend/agents/nodes/add_couple_touch.py`

### P1-8 缺少日期先后校验
- **现象**：`end_date < start_date` 时 `num_days = max(1, ...)` 静默变 1 天行程，无任何信号。
- **修复**：`TripPlanRequest` 加 `model_validator(mode="after")`，在 API 边界拒绝（422）。
- **文件**：`backend/schemas/__init__.py`

### P1-9 结构化抽取用了 temperature=0.7
- **现象**：所有 LLM 调用统一 0.7，含意图/槽位抽取这类应确定的结构化任务，导致结果漂移、加剧 P1-5。
- **修复**：新增 `STRUCTURED_TEMPERATURE=0.1` / `CREATIVE_TEMPERATURE=0.7`；
  `_get_llm(provider, temperature)` 缓存键改 `(provider, temperature)`；
  `call_llm`/`acall_llm`（结构化）用 0.1，`acall_llm_text`（自由文本）保持 0.7。
- **文件**：`backend/services/llm.py`、`backend/tests/test_services.py`

---

## P2 / P3（健壮性 / 死代码 / 优化）

### P2-10 删除死代码 createPlan
- **现象**：`frontend/src/services/plan.ts` 的 `createPlan` 用 `postEventStream` 期望 SSE，
  但后端 POST 返回 JSON；全前端无引用（实际用 `startPlan`/`resumeStream`）。
- **修复**：删除 `createPlan` + `CreatePlanOptions` + 未用的 `postEventStream` 导入。
- **文件**：`frontend/src/services/plan.ts`

### P2-12 health 混淆 liveness/readiness
- **现象**：`/health` 恒 200，降级时编排器无法据此摘流。
- **修复**：新增 `/ready` 就绪探针，降级返回 503；`/health` 保持 200 liveness（不破坏既有 docker healthcheck）。
- **文件**：`backend/api/health.py`

### P2-14 amap 业务错误绕过熔断
- **现象**：`status != "1"`（鉴权/配额等业务错误）在 `resilient_call` **之外**抛出，不触发熔断/重试。
- **修复**：把 `status` 校验移入 `_do_get`，使持续失败的业务错误也能熔断。
- **文件**：`backend/services/amap.py`

### P3-15 send 无在途并发防护
- **修复**：`chatStore.send` 开头判断 `status === "sending"` 时直接返回，防双击/连点重复请求。
- **文件**：`frontend/src/stores/chatStore.ts`

### P3-16 assistant 消息缺 messageId
- **修复**：追加 assistant 气泡时补 `messageId: {messageId}:reply`，与服务端 reply key 对齐。
- **文件**：`frontend/src/stores/chatStore.ts`

### P2-13 熔断器线程安全
- 已并入 P1-4 修复（加锁）。

---

## 未改动（需部署/架构决策）

- **#11 鉴权/IDOR**：`auth_enabled=False` 默认无鉴权、`client_id=None` 列全部会话，属**部署配置决策**
  而非代码 bug（真实前端始终传 `client_id`）。生产上线前建议在配置层开启 `auth_enabled` 与 `rate_limit_enabled`。
- **#21 多 worker SSE**：`plan_streams` 仍是进程内存（代码已注明），横向扩容前需换 Redis/消息中间件——属架构演进。

---

## 验证记录（2026-11-02）

- [x] 后端 `pytest -q`：**465 passed + 3 skipped**（skip 为需真实 PG / `QWX_TEST_REAL_API=1` 的用例）
  - 修复前基线 11 failed（10 个 `test_conversation_e2e` 因 fake store 接口漂移 + 1 个 `test_services` 因温度签名变更），均已随本轮同步修正
- [x] 前端 `npx tsc -p tsconfig.app.json --noEmit`：无错误
- [x] 前端 `npm run check:store`：**28/28 passed**（含 send 并发防护的错误/重试路径断言）

## 变更文件清单（16 个）

后端（12）：
`agents/conversation.py`、`agents/nodes/add_couple_touch.py`、`agents/nodes/output_format.py`、
`api/health.py`、`api/plan.py`、`schemas/__init__.py`、`services/amap.py`、
`services/conversation_store.py`、`services/llm.py`、`services/plan_pipeline.py`、
`services/resilience.py`、`services/storage.py`

后端测试（2）：`tests/fake_conversation_store.py`、`tests/test_services.py`

前端（2）：`src/services/plan.ts`、`src/stores/chatStore.ts`

## 数据库迁移提示

本轮为 `plans` 增加 `client_id`、为 `chat_sessions` 增加 `slots_message_id` / `last_modify_patch`，
均在各自 `_init_ddl` 中以 `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
幂等处理，进程首次访问存储时自动生效，无需手工迁移脚本。既有历史行的 `client_id` 为 `NULL`，
在按具体 `client_id` 过滤时不会被召回（fail-safe，不泄漏）。
