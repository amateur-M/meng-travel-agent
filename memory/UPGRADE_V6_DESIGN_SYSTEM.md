# CoupleTrip V6：设计系统与交互质量 — 执行结果

> 起因：用户给出资深前端工程师规范（统一设计语言、简洁现代、避免过度装饰、控制依赖、完整交互反馈）。
> 范围决策经用户确认三项：
> 1. **零新依赖** —— 不引入 shadcn/ui、Radix、TanStack Query、Magic UI；
> 2. **深色模式跟随系统 + 手动切换并记住选择**；
> 3. **包含更大视觉改版** —— 重做 Chat 消息流与时间轴卡片视觉。
>
> 硬门槛：`tsc -b` + `vite build` 通过 + `npm run check:store` 全绿。
> 关联文档：`ARCHITECTURE.md` §6.3（V6 决策）、`PROGRESS.md`（V6 章节）。

---

## 0. 为什么零新依赖

推荐栈里的组件库/请求库，在**这个代码库**上都会变成负收益，逐条给理由（不是"够用就行"的含糊说法）：

| 候选 | 不引入的理由 |
|------|-------------|
| **shadcn/ui + Radix** | 现有 22 个组件已建立 `.ct-*` 令牌层，且与业务深度耦合（Chat 的水合幂等、`pendingMessageId`、槽位 patch、SSE 三态）。shadcn 是"拷贝源码自己改"的模式，等于重写而非复用；Radix 的价值在 Dialog/Popover/Select 这类无障碍原语，而本项目**只有"删除会话确认"一个真实需求**，原生 `<dialog>` 自带 top-layer、焦点陷阱、ESC、`aria-modal`，40 行且零依赖即可达标 |
| **TanStack Query** | 数据获取全在 `chatStore` 里手写，但承载 V3 的细粒度恢复语义（水合幂等守卫、`hydratedSessionId`、跨标签 `storage` 事件、`message_id` 幂等重试）。迁移到 Query 是**重构**不是升级，会威胁 V3/V5 已经用测试钉死的恢复矩阵 |
| **Magic UI / Aceternity** | 定位是炫技组件（粒子背景、光束、文字滚动）。与"简洁现代、避免过度装饰"直接冲突，且会显著增大 bundle |
| **react-resizable-panel / dnd-kit / Recharts** | 无对应需求：本产品没有可拖拽分区、没有拖拽排序、预算只用进度条不用图表 |

结论：本轮所有产出都是**修断裂 + 收敛令牌**，`package.json` 依赖零变化。

---

## 1. 根因与对策

| 症状 | 根因（真实代码） | V6 对策 |
|------|-----------------|---------|
| 深色模式"半接线" | cream/blush/gold/ink 已变量化，但仍有 **48 处**直接用 Tailwind 原生调色板（`bg-sky-50`/`text-amber-800`/`bg-rose-50`…），这些**不随主题翻转** | 新增 `tone.*` 语义令牌（7 个色调 × 4 个角色），48 处全部迁移 |
| 硬编码 hex | `BudgetBar` 3 个 hex（进度条填充）、`BudgetSlider` 内联渐变 2 个 hex、`index.css` `::selection` | 全部改为 `rgb(var(--x))` |
| 主题不持久 / 不跟随系统 / 白闪 | `uiStore.theme` 硬编码 `"light"`，无 localStorage，无 `prefers-color-scheme`，首帧由浏览器画默认色 | `preference: light\|dark\|system` 持久化 + `watchSystemTheme()` 实时跟随 + `index.html` 内联脚本**首帧前**定主题 |
| 主题切换生硬 | 无过渡 | `.theme-switching` 只在切换的 260ms 内启用颜色过渡（不会拖慢 hover） |
| `reducedMotion` 死代码 | store 里有 flag、有 toggle，**零消费者**；framer-motion 动画完全无视它 | 用 `<MotionConfig reducedMotion="user">` 让全树动画尊重系统设置 |
| 48 处颜色会"漂移" | 无单一来源 | `config/tones.ts` 一处定义，组件只引用 token |

---

## 2. 令牌层设计

### 2.1 分类色（`tone`）

原先 `bg-sky-50 text-sky-700 border-sky-200` 这样的三件套散落在 8 个文件里。现在每个色调（sky/violet/indigo/emerald/amber/orange/rose）只暴露 **4 个角色**：

| 角色 | 用途 | class |
|------|------|-------|
| `soft` | 面板/底色 | `bg-tone-x-soft` |
| `strong` | 面板上的文字/图标，也作独立强调色 | `text-tone-x-strong` |
| `line` | 与面板匹配的边框 | `border-tone-x-line` |
| `fill` | 实心填充（进度条、小徽章） | `bg-tone-x-strong` |

派生组合（`chip` = soft+strong+line，`panel` = soft+line）也在同一文件里。

**关键约束**：所有 class 都是**字面量**。`"bg-" + hue` 这种运行时拼接 Tailwind 扫不到，样式会静默失效 —— 这是这类重构最常见的失败方式，因此 `tones.ts` 里刻意写了 7×6 组展开的字面量。

颜色按**语义**选而非按装饰选：emerald=成功、amber=警告、rose=危险、sky=信息，其余是活动类型。

### 2.2 主题变量翻转规则

| 维度 | light | dark |
|------|-------|------|
| surface / cream | 白 / 奶白 | 深棕（45 35 40 / 36 28 32） |
| ink 文本 | 深 → 浅 | 完全反转 |
| blush / gold 强调阶 | 深字浅底 | **色阶反转**（浅字深底） |
| `--shadow` | 暖近黑 `78 47 55` | 纯黑 `0 0 0`（暖阴影在深底上会消失） |
| `tone-*-soft` | Tailwind 50 阶 | 深色 tint |
| `tone-*-strong` | Tailwind 700 阶 | 浅色 tint（降低饱和，避免霓虹块） |

### 2.3 组件语义类（`index.css` `@layer components`）

| 类 | 用途 |
|----|------|
| `.ct-card` / `.ct-card-flat` | 一级卡片 / 嵌套卡片（无阴影，形成两层深度而非全部悬浮） |
| `.ct-input` | 文本输入（含 focus 环） |
| `.ct-btn-primary` | 主行动（固定 brand 色 + `active:scale-[0.99]`） |
| `.ct-btn-outline` | 次行动（描边） |
| `.ct-btn-quiet` | 行级操作（重命名/删除/点赞） |
| `.ct-btn-icon` | 页头圆角图标按钮 |
| `.ct-chip` | 药丸标签 |
| `.ct-well` | 长文本凹槽 |
| `.ct-scroll` | 主题化细滚动条（原先 15px 灰条是全页最吵的元素） |

统一 **`:focus-visible` 焦点环**（取自 blush 色阶，能随主题翻转），此前每个控件都退回浏览器默认焦点样式，在 blush 底上不可见。

---

## 3. 视觉改版（P2）

### 3.1 Chat 消息流（`ChatWindow`）

| 改动 | 理由 |
|------|------|
| 连续 assistant 消息共享一个头像（后续用等宽 spacer 对齐） | 原先每条都是"头像 + 气泡"的独立行，一段回复被拆成几条时会像好几个人在说话 |
| 仅在**日期变化**处插入分隔线（今天/昨天/9月12日） | 一次对话跨天时没有任何时间锚点 |
| 用户气泡 `rounded-br-md`、助手气泡 `rounded-bl-md` | 尾巴指向发送方，取代原来六个角等圆角的"无方向"气泡 |
| **滚动锚定**：仅在读者已在底部附近时才自动跟随 | 原先 `scrollIntoView` 无条件执行，向上翻历史会被强行拽回底部 |
| 离开底部后出现**"回到最新"** 悬浮药丸 | 让"离开底部"成为可恢复的动作，而不是失去新消息 |
| 打字指示器换成 3 个 1.5px 小点 + `role="status"` | 原 2px 点 + 无 aria，屏幕阅读器不知道正在回复 |

### 3.2 时间轴（`Timeline` / `TimelineCard`）

| 改动 | 理由 |
|------|------|
| 每天头部改为**无卡片外壳**的独立 section，Day 徽章用固定 brand 色 | 原来每天都套一层 card，3 天行程读起来像 3 份独立报告，而不是一份文档的三节 |
| 活动卡片：名称 + 花费同一行，类型/时间/地点降为 meta 行 | 读者真正比较的是"做什么、花多少"；原来 40px 类型色块与标题抢注意力，描述被挤窄 |
| 类型图标缩为 meta 行里的 chip | 同上 |
| 配图与主题占位**统一 4:3 盒**（`h-40`，inline 用 `h-24`） | 原来有图 `h-36` / 无图 `h-24`，图片加载失败会让卡片高度跳变 |
| 图片加底部 scrim | 亮色照片上白字可读 |
| 占位插画用 tone 渐变 | 原来 `from-sky-100 to-indigo-100` 在深色下是刺眼的浅色块 |
| 留白活动保持虚线无配图 | 不喧宾夺主 |
| 卡片 hover 反馈 + `group-focus-within` | 触摸/键盘用户也能触发操作区 |

### 3.3 计划卡片（`ChatPlanCard`）

头部从"三个等重药丸"改为：目的地为标题 + 天数徽章同行、日期副行、右侧预算数值、**hero 内一条发丝级进度条**。目的地是重点，预算只是状态。

### 3.4 空状态（`ChatEmptyState`）

三条快速开始建议**各带图标 + 副标题**（有明确目的地 / 还没有主意 / 周边短途），从"三行一样的文字"变成"三种不同的请求类型"。

---

## 4. 交互与可访问性修复（P3）

| # | 缺陷（真实代码） | 修复 |
|---|-----------------|------|
| 1 | `ChatInput` `rows={1}` + `maxHeight:120px` 只是**上限**，textarea 不会自增，多行想法在一行里滚动 | `useEffect` 量 `scrollHeight` 自适应增高（上限 160px），删除时同步收缩 |
| 2 | `SessionList` 行内操作 `opacity-0 group-hover:opacity-100` → **触屏永不可见**、键盘聚焦也不可见 | 操作常驻布局（`opacity-60`），hover/focus 提到 100%，并补 `aria-label` |
| 3 | `Chat` 根节点 `h-screen`：移动端 `100vh` 含地址栏，composer 被顶到地址栏下 | 改 `h-dvh`（`index.css` 与页面同步，全站 `min-h-screen` → `min-h-dvh`） |
| 4 | `window.confirm` 删除会话：无视主题、阻塞线程、不可样式化 | 新建 `components/ConfirmDialog.tsx`，原生 `<dialog>` + `showModal()`；Cancel 拿初始焦点（破坏性操作不能一个回车就删掉） |
| 5 | 会话列表首屏无加载态 | `SessionSkeleton`（`animate-shimmer` + cream 渐变） |
| 6 | `PlanResult` 返回按钮文案写"重新规划"，实际只是返回对话 | 改"返回对话"，并同步 E2E 断言 |
| 7 | 全站无统一焦点环 | `:focus-visible` 全局规则（blush-400，随主题翻转） |
| 8 | 滚动条 15px 纯灰 | `.ct-scroll` 主题化细滚动条 |
| 9 | 空状态/骨架屏缺 shimmer 动画 | `tailwind.config.ts` 新增 `shimmer`、`fade-up` keyframes |
| 10 | `SlotPanel` 是带标题的独立卡片，composer 成了三层堆叠 | 降为一行可折叠 chip 行，composer 收敛 |

**a11y 补齐**：状态条 `role="alert"` / `role="status"`、输入框 `aria-label`、会话列表 `aria-current`/`aria-label`、展开按钮 `aria-expanded`、点赞 `aria-pressed`、预算滑块 `aria-valuetext`、装饰元素 `aria-hidden`。

---

## 5. 文件清单

**新增（2）**
- `frontend/src/config/tones.ts` —— tone 令牌单一来源（含字面量 class 展开）
- `frontend/src/components/ConfirmDialog.tsx` —— 原生 `<dialog>` 确认框

**修改（25）**
- 令牌/主题：`tailwind.config.ts`、`src/index.css`、`index.html`、`src/App.tsx`、`src/stores/uiStore.ts`、`src/components/ThemeToggle.tsx`
- Chat：`pages/Chat.tsx`、`ChatWindow`、`ChatInput`、`ChatComposer`、`ChatStatusRegion`、`ChatPlanCard`、`ChatEmptyState`、`SessionList`、`SlotPanel`
- 行程：`Timeline`、`TimelineCard`、`ActivityImage`、`WeatherBadge`、`CoupleMessage`、`BudgetBar`、`BudgetAlerts`
- 其他页面/组件：`pages/Loading.tsx`、`pages/PlanResult.tsx`、`pages/Home.tsx`、`SSEProgress`、`StreamingItinerary`、`TripForm/BudgetSlider.tsx`
- E2E：`e2e/full_flow.spec.ts`（"重新规划" → "返回对话"）

**依赖**：`package.json` **零变化**。

---

## 6. 验证记录

| 项 | 命令 | 结果 |
|----|------|------|
| 类型检查 | `npx tsc -b` | 通过（首次 2 个未使用 interface 报错，已删除） |
| 生产构建 | `npm run build` | 通过，2274 modules，CSS 44.50 kB / gzip 8.05 kB，JS gzip 138.52 kB |
| chat store | `npm run check:chat` | **49/49** |
| trip store | `npm run check:store` | **28/28** |
| tone 类生成 | grep 构建产物 | 21 个 `bg/text/border-tone-*` 类**全部存在** |
| 令牌双主题定义 | grep 构建产物 | 每个 `--tone-*`、`--shadow` 均定义 **2 次**（light + dark） |
| 暗色实际取值 | 抽查 `:root[data-theme=dark]` | `--surface: 45 35 40`、`--ink-900: 255 245 247`、`--shadow: 0 0 0`、`--tone-sky-soft: 18 33 45` ✅ 全部翻转 |
| 残留原生调色板 | grep `(bg|text|border|from|to|ring)-(sky|amber|...)-\d+` | **0 处**（仅在 `tones.ts` 内作为注释/映射源） |
| 残留硬编码 hex | grep `#[0-9a-f]{6}` in `*.tsx` | **0 处** |
| `window.confirm` / `h-screen` | grep | 0 处（仅注释提及） |

**为什么用 grep 构建产物而不是截图**：深色模式失效的典型形态是"class 写了但 CSS 没生成"，此时构建和 `tsc` 都是绿的，截图也只在人眼盯到某一块颜色时才看得出。因此直接断言"类存在 + 变量定义两次 + 暗色取值已翻转"，比截图更接近根因。本机无 Playwright 浏览器（沿用 V3/V4/V5 约定），视觉最终确认仍需人工过 `DEPLOY.md` §五 清单。

---

## 7. 遗留

1. **浏览器人工确认仍需执行**：深色模式下逐页过一遍（Chat / 空状态 / 展开行程 / PlanResult / Loading / `/form`）；`DEPLOY.md` §五 清单。
2. **`tripStore` 的 3 个状态色**：本轮未动 `tripStore`（纯状态机，无视觉），其 `progress` 步骤色已随 `SSEProgress` 改完。
2. **E2E 未在本机执行**：Playwright 浏览器未安装，断言已同步更新，仅在 CI 生效。
3. **静态地图 / OTel tracing** 仍为历史遗留，与本轮无关。
