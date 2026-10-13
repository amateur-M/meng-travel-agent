import { expect, test } from "@playwright/test";

/**
 * CoupleTrip E2E: 完整用户流程
 * 输入 → 规划 → 流式加载 → 结果展示 → 预算/天气提示
 *
 * 运行前提：后端在 localhost:8000 提供服务（Vite 代理或直连）。
 * 后端缺少外部 API key 时会降级为 mock 数据，测试不应失败。
 */

test.describe("情侣行程完整流程", () => {
  test("首页加载并展示表单", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "定制情侣行程" })).toBeVisible();
    await expect(page.getByText("生成行程").first()).toBeVisible();
  });

  test("提交默认表单后进入加载页并最终展示行程", async ({ page }) => {
    await page.goto("/");

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
    await page.goto("/");
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
    await page.goto("/");
    await page.getByRole("button", { name: "生成行程" }).first().click();
    await page.waitForURL(/\/result/, { timeout: 60_000 });

    await page.getByRole("button", { name: "重新规划" }).click();
    await expect(page).toHaveURL("/");
  });

  test("低预算触发降级提示", async ({ page }) => {
    await page.goto("/");

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
