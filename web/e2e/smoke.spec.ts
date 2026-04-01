import { expect, test } from "@playwright/test";
import { getBroadRoutes, getRouteManifest } from "./support/manifest";
import {
  expectNoBrokenImages,
  expectNoConsoleErrors,
  gotoAndWait,
  readVisibleHeading,
  trackNetworkFailures,
} from "./support/helpers";

test.describe("Smoke", () => {
  for (const route of getBroadRoutes()) {
    test(`${route.path} renders without runtime failures`, async ({ page }) => {
      const network = trackNetworkFailures(page);

      await expectNoConsoleErrors(page, async () => {
        await gotoAndWait(page, route.path);
      });

      expect(network.failures).toEqual([]);
      network.dispose();
    });
  }

  test("dashboard reflects exported meta data for each format", async ({ page }) => {
    const manifest = getRouteManifest();

    for (const format of manifest.formats) {
      await gotoAndWait(page, `/${format.slug}`);

      const response = await page.request.get(`/data/${format.slug}/meta.json`);
      expect(response.ok()).toBeTruthy();
      const meta = await response.json();

      await expect(page.locator("[data-testid='tier-section']")).toBeVisible();
      await expect(page.locator("[data-testid='archetype-link']").first()).toContainText(meta.archetypes[0].archetype);
      await expect(page.locator("[data-testid='meta-share']").first()).toContainText(
        `${Number(meta.archetypes[0].meta_share).toFixed(1)}%`,
      );
      await expect(
        page.locator("span").filter({ hasText: new RegExp(`${meta.tournament_count}\\s+tournaments`, "i") }),
      ).toBeVisible();
    }
  });

  test("top-level navigation reaches key destinations from the default format", async ({ page }) => {
    const defaultFormat = getRouteManifest().formats[0]?.slug ?? "ninja-spinner";
    await gotoAndWait(page, `/${defaultFormat}`);

    const nav = page.locator("[data-testid='main-nav']");
    await expect(nav).toBeVisible();

    await nav.getByRole("button", { name: "Decks" }).click();
    await page.getByRole("link", { name: "Archetypes" }).first().click();
    await expect(page).toHaveURL(new RegExp(`/${defaultFormat}/archetypes$`));

    await gotoAndWait(page, `/${defaultFormat}`);
    await nav.getByRole("button", { name: "Cards" }).click();
    await page.getByRole("link", { name: "Buy List" }).first().click();
    await expect(page).toHaveURL(new RegExp(`/${defaultFormat}/buylist$`));
  });

  test("representative detail routes expose visible primary headings", async ({ page }) => {
    const manifest = getRouteManifest();

    for (const format of manifest.formats) {
      if (format.topArchetypeSlug) {
        await gotoAndWait(page, `/${format.slug}/archetypes/${format.topArchetypeSlug}`);
        expect(await readVisibleHeading(page)).not.toEqual("");
      }

      if (format.topCardSlug) {
        await gotoAndWait(page, `/${format.slug}/cards/${format.topCardSlug}`);
        expect(await readVisibleHeading(page)).not.toEqual("");
      }
    }
  });

  test("default dashboard has no broken rendered images", async ({ page }) => {
    const defaultFormat = getRouteManifest().formats[0]?.slug ?? "ninja-spinner";
    await gotoAndWait(page, `/${defaultFormat}`);
    await expectNoBrokenImages(page);
  });
});
