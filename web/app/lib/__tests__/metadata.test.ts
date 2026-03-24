import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("fs", () => ({
  default: {
    readFileSync: vi.fn(),
    readdirSync: vi.fn(),
    existsSync: vi.fn(() => true),
  },
  readFileSync: vi.fn(),
  readdirSync: vi.fn(),
  existsSync: vi.fn(() => true),
}));

import fs from "fs";
import { getArchetype, getCardDetail, getFormatName } from "../data";
import { formatPageMetadata, safePercent, safeInt } from "../metadata";

const MOCK_FORMATS = [
  {
    slug: "ninja-spinner",
    name: "忍スピナー",
    name_en: "Ninja Spinner",
    description: "Test",
    dataset_start: "2026-03-01",
    dataset_end: "2026-06-01",
    status: "active",
  },
];

function mockArch(overrides: Record<string, unknown> = {}) {
  return {
    archetype: "Test Archetype",
    slug: "test-archetype",
    meta_share: 10.0,
    weighted_share: 12.0,
    deck_count: 20,
    best_placement: 1,
    tier: "A",
    core_cards: [],
    all_cards: [],
    results: [],
    sprite_filenames: [],
    ...overrides,
  };
}

function mockCard(overrides: Record<string, unknown> = {}) {
  return {
    card_name: "Test Card",
    slug: "test-card",
    usage_pct: 50.0,
    unique_archetypes: 5,
    avg_copies: 2,
    category: "Trainer",
    top_archetypes: [],
    weekly_usage: [],
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fs.existsSync).mockReturnValue(true);
});

describe("safePercent", () => {
  it("formats a finite number to one decimal place", () => {
    expect(safePercent(15.3)).toBe("15.3");
    expect(safePercent(0)).toBe("0.0");
    expect(safePercent(100)).toBe("100.0");
  });

  it("returns '0.0' for NaN", () => {
    expect(safePercent(NaN)).toBe("0.0");
  });

  it("returns '0.0' for Infinity", () => {
    expect(safePercent(Infinity)).toBe("0.0");
    expect(safePercent(-Infinity)).toBe("0.0");
  });
});

describe("safeInt", () => {
  it("returns the value when finite", () => {
    expect(safeInt(42)).toBe(42);
    expect(safeInt(0)).toBe(0);
  });

  it("returns 0 for NaN", () => {
    expect(safeInt(NaN)).toBe(0);
  });

  it("returns 0 for Infinity", () => {
    expect(safeInt(Infinity)).toBe(0);
    expect(safeInt(-Infinity)).toBe(0);
  });
});

describe("formatPageMetadata", () => {
  it("resolves format name and passes it to the builder", async () => {
    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(MOCK_FORMATS));
    const result = await formatPageMetadata(
      Promise.resolve({ format: "ninja-spinner" }),
      (formatName) => ({
        title: `Test -- ${formatName} | Scout`,
        description: `Desc for ${formatName}`,
      }),
    );
    expect(result.title).toBe("Test -- Ninja Spinner | Scout");
    expect(result.description).toBe("Desc for Ninja Spinner");
  });

  it("throws when format is unknown", async () => {
    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(MOCK_FORMATS));
    await expect(
      formatPageMetadata(
        Promise.resolve({ format: "unknown-format" }),
        (formatName) => ({ title: formatName, description: "" }),
      ),
    ).rejects.toThrow('format "unknown-format" not found');
  });
});

describe("archetype metadata formatting", () => {
  function buildArchetypeMetadata(format: string, slug: string) {
    const arch = getArchetype(format, slug);
    const share = safePercent(arch.meta_share);
    const formatName = getFormatName(format);
    return {
      title: `${arch.archetype} -- ${share}% Meta Share, Tier ${arch.tier ?? "Unranked"} | Scout`,
      description: `${arch.archetype} in ${formatName}: ${share}% meta share, Tier ${arch.tier ?? "Unranked"}, ${safeInt(arch.deck_count)} decks. Core cards, results, and performance analysis.`,
    };
  }

  function setupArchMocks(overrides: Record<string, unknown> = {}) {
    vi.mocked(fs.readFileSync)
      .mockReturnValueOnce(JSON.stringify(mockArch(overrides)))
      .mockReturnValueOnce(JSON.stringify(MOCK_FORMATS));
  }

  it("formats title and description correctly", () => {
    setupArchMocks({ archetype: "Charizard ex", slug: "charizard-ex", meta_share: 15.3, weighted_share: 18.2, deck_count: 42, tier: "S" });

    const meta = buildArchetypeMetadata("ninja-spinner", "charizard-ex");
    expect(meta.title).toBe("Charizard ex -- 15.3% Meta Share, Tier S | Scout");
    expect(meta.description).toBe(
      "Charizard ex in Ninja Spinner: 15.3% meta share, Tier S, 42 decks. Core cards, results, and performance analysis."
    );
  });

  it("handles NaN meta_share gracefully", () => {
    setupArchMocks({ archetype: "Bad Data", meta_share: NaN, tier: "Rogue" });

    const meta = buildArchetypeMetadata("ninja-spinner", "bad-data");
    expect(meta.title).toBe("Bad Data -- 0.0% Meta Share, Tier Rogue | Scout");
    expect(meta.title).not.toContain("NaN");
  });

  it("handles NaN deck_count gracefully", () => {
    setupArchMocks({ archetype: "Broken Deck", deck_count: NaN, tier: "B" });

    const meta = buildArchetypeMetadata("ninja-spinner", "broken-deck");
    expect(meta.description).toContain("0 decks");
    expect(meta.description).not.toContain("NaN");
  });

  it("handles missing tier gracefully", () => {
    setupArchMocks({ archetype: "No Tier", tier: undefined });

    const meta = buildArchetypeMetadata("ninja-spinner", "no-tier");
    expect(meta.title).toContain("Tier Unranked");
    expect(meta.title).not.toContain("undefined");
  });
});

describe("card metadata formatting", () => {
  function buildCardMetadata(format: string, slug: string) {
    const card = getCardDetail(format, slug);
    const usage = safePercent(card.usage_pct);
    const formatName = getFormatName(format);
    return {
      title: `${card.card_name} -- ${usage}% Usage | Scout`,
      description: `${card.card_name} appears in ${usage}% of ${formatName} decks across ${safeInt(card.unique_archetypes)} archetypes. Usage trends, synergy partners, and decklist data.`,
    };
  }

  function setupCardMocks(overrides: Record<string, unknown> = {}) {
    vi.mocked(fs.readFileSync)
      .mockReturnValueOnce(JSON.stringify(mockCard(overrides)))
      .mockReturnValueOnce(JSON.stringify(MOCK_FORMATS));
  }

  it("formats title and description correctly", () => {
    setupCardMocks({ card_name: "Boss's Orders", slug: "bosss-orders", usage_pct: 62.4, unique_archetypes: 8 });

    const meta = buildCardMetadata("ninja-spinner", "bosss-orders");
    expect(meta.title).toBe("Boss's Orders -- 62.4% Usage | Scout");
    expect(meta.description).toBe(
      "Boss's Orders appears in 62.4% of Ninja Spinner decks across 8 archetypes. Usage trends, synergy partners, and decklist data."
    );
  });

  it("handles NaN usage_pct gracefully", () => {
    setupCardMocks({ card_name: "Bad Card", usage_pct: NaN });

    const meta = buildCardMetadata("ninja-spinner", "bad-card");
    expect(meta.title).toBe("Bad Card -- 0.0% Usage | Scout");
    expect(meta.title).not.toContain("NaN");
  });

  it("handles NaN unique_archetypes gracefully", () => {
    setupCardMocks({ card_name: "Broken Card", unique_archetypes: NaN });

    const meta = buildCardMetadata("ninja-spinner", "broken-card");
    expect(meta.description).toContain("across 0 archetypes");
    expect(meta.description).not.toContain("NaN");
  });
});
