import { test, expect } from "@playwright/test";

test.describe("Card Analysis (Format Edge)", () => {
  test("loads and shows card rows", async ({ page }) => {
    await page.goto("/ninja-spinner/card-analysis");

    const rows = page.locator("[data-testid='card-row']");
    await expect(rows.first()).toBeVisible({ timeout: 10_000 });
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);
  });

  test("clicking a card expands archetype breakdown", async ({ page }) => {
    await page.goto("/ninja-spinner/card-analysis");

    const firstRow = page.locator("[data-testid='card-row']").first();
    await firstRow.locator("button").click();

    const breakdown = page
      .locator("[data-testid='archetype-breakdown']")
      .first();
    await expect(breakdown).toBeVisible();
  });
});
