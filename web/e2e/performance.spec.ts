import { expect, test } from "@playwright/test";
import { getPerformanceRoutes } from "./support/manifest";
import { collectPerformanceMetrics, gotoAndWait } from "./support/helpers";

test.describe("Performance", () => {
  for (const route of getPerformanceRoutes()) {
    test(`${route.path} stays within budget`, async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await gotoAndWait(page, route.path);
      const metrics = await collectPerformanceMetrics(page);

      expect(metrics.lcpMs, `${route.path} LCP`).not.toBeNull();
      expect(metrics.domCompleteMs, `${route.path} domComplete`).not.toBeNull();
      expect(metrics.lcpMs ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(route.budget.lcpMs);
      expect(metrics.domCompleteMs ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(route.budget.domCompleteMs);
      expect(metrics.totalBytes).toBeLessThanOrEqual(route.budget.totalBytes);
      expect(metrics.resourceCount).toBeLessThanOrEqual(route.budget.resourceCount);
      expect(metrics.imageCount).toBeLessThanOrEqual(route.budget.imageCount);
    });
  }
});
