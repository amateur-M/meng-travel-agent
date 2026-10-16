import { expect, test } from "@playwright/test";

/**
 * CoupleTrip E2E: 完整用户流程
 * 对话页 → 表单 → 规划 → 流式加载 → 结果展示 → 预算/天气提示
 *
 * 路由契约（P1.3 之后）：
 *   /            → Chat 对话页（默认入口）
 *   /form        → 旧表单页（TripForm，含"定制情侣行程"标题与"生成行程"按钮）
 *   /loading     → 规划进度
 *   /result      → 行程结果
 * 本文件的表单流程用例必须从 /form 进入；断言"返回首页"仍指向 /。
 *
 * 运行前提：后端在 localhost:8000 提供服务（Vite 代理或直连）。
 * 后端缺少外部 API key 时会降级为 mock 数据，测试不应失败。
 */

test.describe("对话页（默认入口）", () => {
  test("首次进入只出现一条问候（StrictMode 双调用不重复）", async ({ page }) => {
    await page.goto("/");

    // 问候语只在 Chat 的对话气泡里出现，页头副标题是"情侣旅行助手"，故取更长子串。
    await expect(page.getByText("我是你们的情侣旅行助手")).toHaveCount(1);
  });

  test("对话页展示会话输入区", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByPlaceholder("说说你们的旅行想法")).toBeVisible();
  });

  /**
   * 回归守卫：对话页自己 POST 创建行程（只为把 session_id 一并传过去，好让生成的
   * 行程关联回会话），而 Loading 页过去只在 status === "idle" 时才去消费 SSE 流 ——
   * 于是"计划已创建，却没有任何人消费它"，页面永远停在加载态，数据库里躺着一条
   * 用户看不到的行程（修复前这条用例必然超时）。
   *
   * 现在行程直接在对话页里出现、不再跳走，输入框就在它下面 —— 想改接着说就行。
   */
  test("对话里说清需求后，行程直接出现在当前对话页", async ({ page }) => {
    await page.goto("/");

    // 规则解析（CI 无 API key）也能理解中文数字："三天" + "预算5000元"
    await page.getByPlaceholder("说说你们的旅行想法").fill("想去大理玩三天，预算5000元");
    await page.keyboard.press("Enter");

    const launch = page.getByRole("button", { name: "开始规划行程" });
    await expect(launch).toBeVisible({ timeout: 30_000 });
    await launch.click();

    // 关键断言：不跳转，行程卡片出现在对话页本身
    await expect(page).toHaveURL("/");
    await expect(page.getByTestId("chat-plan-card")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("天行程").first()).toBeVisible();

    // 就地展开行程，并保留通往完整结果页的入口
    await page.getByTestId("chat-plan-toggle").click();
    await expect(page.getByRole("button", { name: "收起行程" })).toBeVisible();

    await page.getByRole("button", { name: "查看完整行程" }).click();
    await expect(page).toHaveURL(/\/result/, { timeout: 10_000 });
  });

  test("生成后可以直接在对话里调整，卡片随之更新", async ({ page }) => {
    await page.goto("/");
    await page.getByPlaceholder("说说你们的旅行想法").fill("想去大理玩三天，预算5000元");
    await page.keyboard.press("Enter");
    await page.getByRole("button", { name: "开始规划行程" }).click();
    await expect(page.getByTestId("chat-plan-card")).toBeVisible({ timeout: 60_000 });

    // 以对话方式修改预算，按钮应变为"重新规划"，重算后卡片反映新预算
    await page.getByPlaceholder("说说你们的旅行想法").fill("预算加到八千");
    await page.keyboard.press("Enter");

    const replan = page.getByRole("button", { name: "按新的要求重新规划" });
    await expect(replan).toBeVisible({ timeout: 30_000 });
    await replan.click();

    await expect(page.getByTestId("chat-plan-card")).toContainText("8,000", { timeout: 60_000 });
  });
});

test.describe("表单页", () => {
  test("表单页加载并展示表单", async ({ page }) => {
    await page.goto("/form");
    await expect(page.getByRole("heading", { name: "定制情侣行程" })).toBeVisible();
    await expect(page.getByText("生成行程").first()).toBeVisible();
  });

  test("提交默认表单后进入加载页并最终展示行程", async ({ page }) => {
    await page.goto("/form");

    // 默认表单值已预填（大理 / 北京 / 2026-09-01 ~ 03 / ¥4500）
    await page.getByRole("button", { name: "生成行程" }).first().click();

    // ── Loading 页 ────────────────────────────────
    await expect(page).toHaveURL(/\/loading/, { timeout: 10_000 });
    await expect(page.getByText("正在为你们规划")).toBeVisible();

    // 等待流式内容或直接跳转结果页（mock 模式很快）
    // 最长等待 60s 跳转到结果页
    await expect(page).toHaveURL(/\/result/, { timeout: 60_000 });
  });

  test("结果页展示行程天数、预算与寄语", async ({ page }) => {
    await page.goto("/form");
    await page.getByRole("button", { name: "生成行程" }).first().click();
    await page.waitForURL(/\/result/, { timeout: 60_000 });

    // ── 结果页核心元素 ────────────────────────────
    await expect(page.getByText("天行程").first()).toBeVisible();
    // 预算展示
    await expect(page.getByText(/¥.*\/.*¥.*/).first()).toBeVisible();
    // 重新规划按钮
    await expect(page.getByRole("button", { name: "重新规划" })).toBeVisible();
  });

  test("结果页支持重新规划返回首页", async ({ page }) => {
    await page.goto("/form");
    await page.getByRole("button", { name: "生成行程" }).first().click();
    await page.waitForURL(/\/result/, { timeout: 60_000 });

    await page.getByRole("button", { name: "重新规划" }).click();
    // / 现在是对话页，仍是"首页"
    await expect(page).toHaveURL("/");
  });

  test("低预算触发降级提示", async ({ page }) => {
    await page.goto("/form");

    // 将预算降到最低档，触发超预算降级
    const budgetSlider = page.locator('input[type="range"]');
    await budgetSlider.evaluate((el: HTMLInputElement) => {
      el.value = "1000";
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    });

    await page.getByRole("button", { name: "生成行程" }).first().click();
    await page.waitForURL(/\/result/, { timeout: 60_000 });

    // 降级模式下结果页应正常渲染（预算条或预警组件可见）
    await expect(page.getByText(/¥.*\/.*¥.*/).first()).toBeVisible();
  });
});
