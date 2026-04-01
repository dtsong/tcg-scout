import { expect, test } from "@playwright/test";
import { getVisualRoutes } from "./support/manifest";
import { gotoAndWait } from "./support/helpers";

test.describe("Render", () => {
  for (const route of getVisualRoutes()) {
    test(`${route.name} matches snapshot`, async ({ page }) => {
      await page.setViewportSize(route.viewport);
      await gotoAndWait(page, route.path);
      await expect(page).toHaveScreenshot(`${route.name}.png`, {
        fullPage: route.viewport.width < 500,
      });
    });
  }
});
