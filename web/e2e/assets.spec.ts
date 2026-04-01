import { expect, test } from "@playwright/test";
import { getBroadRoutes, getRouteManifest } from "./support/manifest";
import { expectNoBrokenImages, gotoAndWait, trackNetworkFailures } from "./support/helpers";

test.describe("Assets", () => {
  for (const route of getBroadRoutes()) {
    test(`${route.path} loads page-critical assets`, async ({ page }) => {
      const network = trackNetworkFailures(page);
      await gotoAndWait(page, route.path);
      await expectNoBrokenImages(page);
      expect(network.failures).toEqual([]);
      network.dispose();
    });
  }

  test("sprite images referenced by meta.json exist on disk", async ({ page }) => {
    for (const format of getRouteManifest().formats) {
      const response = await page.request.get(`/data/${format.slug}/meta.json`);
      expect(response.ok()).toBeTruthy();
      const meta = await response.json();

      for (const archetype of meta.archetypes.slice(0, 20)) {
        for (const spriteFilename of archetype.sprite_filenames ?? []) {
          const spriteResponse = await page.request.get(`/images/sprites/${spriteFilename}`);
          expect(spriteResponse.ok(), `${format.slug}:${spriteFilename}`).toBeTruthy();
        }
      }
    }
  });
});
