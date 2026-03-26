import { test } from "@playwright/test";

const SCREENSHOT_DIR = "screenshots";

test.describe("Release Screenshots", () => {
  test.use({
    viewport: { width: 1440, height: 900 },
    colorScheme: "dark",
  });

  test("format dashboard -- hero + tier list + rogue spotlight", async ({
    page,
  }) => {
    await page.goto("/ninja-spinner");
    await page.waitForLoadState("networkidle");
    // Give animations time to settle
    await page.waitForTimeout(1000);
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/dashboard-hero.png`,
      fullPage: false,
    });
  });

  test("format dashboard -- full page", async ({ page }) => {
    await page.goto("/ninja-spinner");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/dashboard-full.png`,
      fullPage: true,
    });
  });

  test("matchup heat matrix", async ({ page }) => {
    await page.goto("/ninja-spinner/matchups");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/matchup-matrix.png`,
      fullPage: false,
    });
  });

  test("archetype detail -- dragapult dusknoir", async ({ page }) => {
    await page.goto("/ninja-spinner/archetypes/dragapult-dusknoir");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/archetype-detail.png`,
      fullPage: false,
    });
  });

  test("archetype detail -- scrolled to matchups section", async ({
    page,
  }) => {
    await page.goto("/ninja-spinner/archetypes/dragapult-dusknoir");
    await page.waitForLoadState("networkidle");
    // Try to scroll to matchup section
    const matchupSection = page.locator("text=Key Matchups").first();
    if (await matchupSection.isVisible()) {
      await matchupSection.scrollIntoViewIfNeeded();
      await page.waitForTimeout(500);
    }
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/archetype-matchups.png`,
      fullPage: false,
    });
  });

  test("mobile dashboard", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/ninja-spinner");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/mobile-dashboard.png`,
      fullPage: false,
    });
  });

  test("mobile nav open", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/ninja-spinner");
    await page.waitForLoadState("networkidle");
    // Open hamburger menu
    const menuButton = page.locator("button[aria-label*='menu' i]").first();
    if (await menuButton.isVisible()) {
      await menuButton.click();
      await page.waitForTimeout(500);
    }
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/mobile-nav.png`,
      fullPage: false,
    });
  });

  test("quickstart page", async ({ page }) => {
    await page.goto("/start");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/quickstart.png`,
      fullPage: false,
    });
  });
});
