import { describe, it, expect, vi } from "vitest";
import { archetypeOgMetadata, dashboardOgMetadata } from "../og";
import type { ArchetypeDetail, MetaData } from "../types";

function mockArchDetail(overrides: Partial<ArchetypeDetail> = {}): ArchetypeDetail {
  return {
    archetype: "Charizard Pidgeot",
    slug: "charizard-pidgeot",
    tier: "S",
    meta_share: 15.3,
    weighted_share: 18.2,
    deck_count: 42,
    best_placement: 1,
    sprite_filenames: ["charizard.png", "pidgeot.png"],
    core_cards: [],
    all_cards: [],
    results: [],
    ...overrides,
  };
}

function mockMeta(overrides: Partial<MetaData> = {}): MetaData {
  return {
    generated_at: "2026-03-26T00:00:00Z",
    tournament_count: 100,
    deck_count: 500,
    date_range: { start: "2026-01-01", end: "2026-03-26" },
    rotation_date: "2026-01-01",
    tier_thresholds: {},
    archetypes: [
      {
        archetype: "Charizard Pidgeot",
        slug: "charizard-pidgeot",
        meta_share: 15.3,
        deck_count: 42,
        best_placement: 1,
        tier: "S",
        sprite_filenames: ["charizard.png", "pidgeot.png"],
      },
      {
        archetype: "Dragapult ex",
        slug: "dragapult-ex",
        meta_share: 10.1,
        deck_count: 30,
        best_placement: 1,
        tier: "S",
        sprite_filenames: ["dragapult.png"],
      },
    ],
    ...overrides,
  };
}

describe("archetypeOgMetadata", () => {
  it("returns correct title and description", () => {
    const result = archetypeOgMetadata("ninja-spinner", "Ninja Spinner", mockArchDetail(), "charizard-pidgeot");
    expect(result.title).toBe("Charizard Pidgeot -- 15.3% Meta Share, Tier S | Scout");
    expect(result.description).toContain("Charizard Pidgeot in Ninja Spinner");
    expect(result.description).toContain("15.3% meta share");
    expect(result.description).toContain("42 decks");
  });

  it("includes OpenGraph metadata", () => {
    const result = archetypeOgMetadata("ninja-spinner", "Ninja Spinner", mockArchDetail(), "charizard-pidgeot");
    const og = result.openGraph as Record<string, unknown>;
    expect(og.title).toBe("Charizard Pidgeot -- 15.3% Meta Share, Tier S | Scout");
    expect(og.url).toBe("https://scout.trainerlab.io/ninja-spinner/archetypes/charizard-pidgeot");
    expect(og.siteName).toBe("Scout");
    expect(og.type).toBe("article");
  });

  it("includes sprite image in OpenGraph and Twitter metadata", () => {
    const result = archetypeOgMetadata("ninja-spinner", "Ninja Spinner", mockArchDetail(), "charizard-pidgeot");
    const og = result.openGraph as Record<string, unknown>;
    const images = og.images as Array<{ url: string }>;
    expect(images[0].url).toBe("https://scout.trainerlab.io/images/sprites/charizard.png");

    const twitter = result.twitter as Record<string, unknown>;
    const twitterImages = twitter.images as string[];
    expect(twitterImages[0]).toBe("https://scout.trainerlab.io/images/sprites/charizard.png");
  });

  it("omits images when no sprite_filenames", () => {
    const arch = mockArchDetail({ sprite_filenames: [] });
    const result = archetypeOgMetadata("ninja-spinner", "Ninja Spinner", arch, "charizard-pidgeot");
    const og = result.openGraph as Record<string, unknown>;
    expect(og.images).toBeUndefined();
  });

  it("falls back to humanized slug when archetype name is empty", () => {
    const arch = mockArchDetail({ archetype: "" });
    const result = archetypeOgMetadata("ninja-spinner", "Ninja Spinner", arch, "charizard-pidgeot");
    expect(result.title).toContain("Charizard Pidgeot -- ");
  });

  it("handles NaN meta_share gracefully", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const arch = mockArchDetail({ meta_share: NaN });
    const result = archetypeOgMetadata("ninja-spinner", "Ninja Spinner", arch, "charizard-pidgeot");
    expect(result.title).toContain("0.0% Meta Share");
    expect(result.title).not.toContain("NaN");
    spy.mockRestore();
  });

  it("includes twitter card as summary_large_image", () => {
    const result = archetypeOgMetadata("ninja-spinner", "Ninja Spinner", mockArchDetail(), "charizard-pidgeot");
    const twitter = result.twitter as Record<string, unknown>;
    expect(twitter.card).toBe("summary_large_image");
  });
});

describe("dashboardOgMetadata", () => {
  it("returns correct title", () => {
    const result = dashboardOgMetadata("ninja-spinner", "Ninja Spinner", mockMeta());
    expect(result.title).toBe("Meta Dashboard -- Ninja Spinner | Scout");
  });

  it("includes top archetype names in description", () => {
    const result = dashboardOgMetadata("ninja-spinner", "Ninja Spinner", mockMeta());
    expect(result.description).toContain("Charizard Pidgeot");
    expect(result.description).toContain("Dragapult ex");
    expect(result.description).toContain("100 tournaments");
    expect(result.description).toContain("500 decks");
  });

  it("includes OpenGraph metadata with correct URL", () => {
    const result = dashboardOgMetadata("ninja-spinner", "Ninja Spinner", mockMeta());
    const og = result.openGraph as Record<string, unknown>;
    expect(og.url).toBe("https://scout.trainerlab.io/ninja-spinner");
    expect(og.type).toBe("website");
    expect(og.siteName).toBe("Scout");
  });

  it("uses top archetype sprite as image", () => {
    const result = dashboardOgMetadata("ninja-spinner", "Ninja Spinner", mockMeta());
    const og = result.openGraph as Record<string, unknown>;
    const images = og.images as Array<{ url: string }>;
    expect(images[0].url).toBe("https://scout.trainerlab.io/images/sprites/charizard.png");
  });

  it("handles null meta gracefully", () => {
    const result = dashboardOgMetadata("ninja-spinner", "Ninja Spinner", null);
    expect(result.title).toBe("Meta Dashboard -- Ninja Spinner | Scout");
    expect(result.description).toContain("Latest meta tier list for Ninja Spinner");
    const og = result.openGraph as Record<string, unknown>;
    expect(og.images).toBeUndefined();
  });

  it("handles meta with empty archetypes", () => {
    const meta = mockMeta({ archetypes: [] });
    const result = dashboardOgMetadata("ninja-spinner", "Ninja Spinner", meta);
    expect(result.description).toContain("Latest meta tier list for Ninja Spinner");
  });

  it("includes twitter card as summary_large_image", () => {
    const result = dashboardOgMetadata("ninja-spinner", "Ninja Spinner", mockMeta());
    const twitter = result.twitter as Record<string, unknown>;
    expect(twitter.card).toBe("summary_large_image");
  });
});
