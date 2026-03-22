import { test, expect } from "@playwright/test";

test.describe("No Regressions", () => {
  const pages = [
    "/ninja-spinner",
    "/ninja-spinner/archetypes",
    "/ninja-spinner/buylist",
    "/ninja-spinner/card-analysis",
    "/ninja-spinner/trends",
  ];

  for (const url of pages) {
    test(`${url} loads without console errors`, async ({ page }) => {
      const errors: string[] = [];
      page.on("console", (msg) => {
        if (msg.type() === "error") errors.push(msg.text());
      });
      page.on("pageerror", (err) => errors.push(err.message));

      await page.goto(url);
      await page.waitForLoadState("domcontentloaded");

      // Filter benign errors (favicon, hydration warnings in dev)
      const real = errors.filter(
        (e) => !e.includes("favicon") && !e.includes("404"),
      );
      expect(real).toEqual([]);
    });
  }

  test("no broken images on dashboard", async ({ page }) => {
    await page.goto("/ninja-spinner");
    await page.waitForLoadState("domcontentloaded");

    // Wait a moment for images to load
    await page.waitForTimeout(2000);

    const brokenImages = await page.evaluate(() => {
      const imgs = Array.from(document.querySelectorAll("img"));
      return imgs
        .filter((img) => img.complete && img.naturalWidth === 0)
        .map((img) => img.src);
    });
    expect(brokenImages).toEqual([]);
  });
});
