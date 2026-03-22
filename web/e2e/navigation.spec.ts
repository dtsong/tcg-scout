import { test, expect } from "@playwright/test";

test.describe("Navigation", () => {
  test("nav bar renders", async ({ page }) => {
    await page.goto("/ninja-spinner");

    const nav = page.locator("[data-testid='main-nav']");
    await expect(nav).toBeVisible();
  });

  test("can navigate to archetypes page", async ({ page }) => {
    await page.goto("/ninja-spinner");

    // Use the nav dropdown button specifically
    const nav = page.locator("[data-testid='main-nav']");
    await nav.getByRole("button", { name: "Decks" }).click();
    await page.getByRole("link", { name: "Archetypes" }).first().click();
    await expect(page).toHaveURL(/\/ninja-spinner\/archetypes/);
  });

  test("can navigate to buy list", async ({ page }) => {
    await page.goto("/ninja-spinner");

    const nav = page.locator("[data-testid='main-nav']");
    await nav.getByRole("button", { name: "Cards" }).click();
    await page.getByRole("link", { name: "Buy List" }).first().click();
    await expect(page).toHaveURL(/\/ninja-spinner\/buylist/);
  });

  test("can navigate to trends", async ({ page }) => {
    await page.goto("/ninja-spinner");

    const nav = page.locator("[data-testid='main-nav']");
    await nav.getByRole("button", { name: "Meta" }).click();
    await page.getByRole("link", { name: "Trends" }).first().click();
    await expect(page).toHaveURL(/\/ninja-spinner\/trends/);
  });
});
