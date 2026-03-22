import { test, expect } from "@playwright/test";

test.describe("Dashboard", () => {
  test("shows tier list with archetypes", async ({ page }) => {
    await page.goto("/ninja-spinner");

    const tierSection = page.locator("[data-testid='tier-section']");
    await expect(tierSection).toBeVisible();

    // At least one archetype link
    const links = page.locator("[data-testid='archetype-link']");
    await expect(links.first()).toBeVisible();
    const count = await links.count();
    expect(count).toBeGreaterThan(0);
  });

  test("archetype links point to detail pages", async ({ page }) => {
    await page.goto("/ninja-spinner");

    const firstLink = page.locator("[data-testid='archetype-link']").first();
    await expect(firstLink).toHaveAttribute(
      "href",
      /\/ninja-spinner\/archetypes\/.+/,
    );
  });

  test("meta share values are numeric percentages", async ({ page }) => {
    await page.goto("/ninja-spinner");

    const share = page.locator("[data-testid='meta-share']").first();
    const text = await share.textContent();
    expect(text).toMatch(/\d+\.?\d*%/);
  });

  test("navigates to archetype detail on click", async ({ page }) => {
    await page.goto("/ninja-spinner");

    const firstLink = page.locator("[data-testid='archetype-link']").first();
    await firstLink.click();
    await expect(page).toHaveURL(/\/ninja-spinner\/archetypes\/.+/);
  });

  test("shows tournament and deck stats", async ({ page }) => {
    await page.goto("/ninja-spinner");
    // Hero section has tournament/deck count spans
    await expect(
      page.locator("span").filter({ hasText: "Tournaments" }),
    ).toBeVisible();
    await expect(
      page.locator("th").filter({ hasText: "Decks" }),
    ).toBeVisible();
  });
});
