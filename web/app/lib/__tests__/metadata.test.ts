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
import { safePercent } from "../metadata";

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

describe("archetype metadata formatting", () => {
  function buildArchetypeMetadata(format: string, slug: string) {
    const arch = getArchetype(format, slug);
    const share = safePercent(arch.meta_share);
    const formatName = getFormatName(format);
    return {
      title: `${arch.archetype} -- ${share}% Meta Share, Tier ${arch.tier ?? "Unranked"} | Scout`,
      description: `${arch.archetype} in ${formatName}: ${share}% meta share, Tier ${arch.tier ?? "Unranked"}, ${Number.isFinite(arch.deck_count) ? arch.deck_count : 0} decks. Core cards, results, and performance analysis.`,
    };
  }

  it("formats title and description correctly", () => {
    const mockArch = {
      archetype: "Charizard ex",
      slug: "charizard-ex",
      meta_share: 15.3,
      weighted_share: 18.2,
      deck_count: 42,
      best_placement: 1,
      tier: "S",
      core_cards: [],
      all_cards: [],
      results: [],
      sprite_filenames: [],
    };

    // First call reads archetype JSON, second reads formats JSON
    vi.mocked(fs.readFileSync)
      .mockReturnValueOnce(JSON.stringify(mockArch))
      .mockReturnValueOnce(JSON.stringify(MOCK_FORMATS));

    const meta = buildArchetypeMetadata("ninja-spinner", "charizard-ex");
    expect(meta.title).toBe("Charizard ex -- 15.3% Meta Share, Tier S | Scout");
    expect(meta.description).toBe(
      "Charizard ex in Ninja Spinner: 15.3% meta share, Tier S, 42 decks. Core cards, results, and performance analysis."
    );
  });

  it("handles NaN meta_share gracefully", () => {
    const mockArch = {
      archetype: "Bad Data",
      slug: "bad-data",
      meta_share: NaN,
      deck_count: 0,
      best_placement: 1,
      tier: "Rogue",
      core_cards: [],
      all_cards: [],
      results: [],
      sprite_filenames: [],
    };

    vi.mocked(fs.readFileSync)
      .mockReturnValueOnce(JSON.stringify(mockArch))
      .mockReturnValueOnce(JSON.stringify(MOCK_FORMATS));

    const meta = buildArchetypeMetadata("ninja-spinner", "bad-data");
    expect(meta.title).toBe("Bad Data -- 0.0% Meta Share, Tier Rogue | Scout");
    expect(meta.title).not.toContain("NaN");
  });

  it("handles NaN deck_count gracefully", () => {
    const mockArch = {
      archetype: "Broken Deck",
      slug: "broken-deck",
      meta_share: 5.0,
      deck_count: NaN,
      best_placement: 1,
      tier: "B",
      core_cards: [],
      all_cards: [],
      results: [],
      sprite_filenames: [],
    };

    vi.mocked(fs.readFileSync)
      .mockReturnValueOnce(JSON.stringify(mockArch))
      .mockReturnValueOnce(JSON.stringify(MOCK_FORMATS));

    const meta = buildArchetypeMetadata("ninja-spinner", "broken-deck");
    expect(meta.description).toContain("0 decks");
    expect(meta.description).not.toContain("NaN");
  });

  it("handles missing tier gracefully", () => {
    const mockArch = {
      archetype: "No Tier",
      slug: "no-tier",
      meta_share: 1.0,
      deck_count: 3,
      best_placement: 1,
      core_cards: [],
      all_cards: [],
      results: [],
      sprite_filenames: [],
    };

    vi.mocked(fs.readFileSync)
      .mockReturnValueOnce(JSON.stringify(mockArch))
      .mockReturnValueOnce(JSON.stringify(MOCK_FORMATS));

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
      description: `${card.card_name} appears in ${usage}% of ${formatName} decks across ${Number.isFinite(card.unique_archetypes) ? card.unique_archetypes : 0} archetypes. Usage trends, synergy partners, and decklist data.`,
    };
  }

  it("formats title and description correctly", () => {
    const mockCard = {
      card_name: "Boss's Orders",
      slug: "bosss-orders",
      usage_pct: 62.4,
      unique_archetypes: 8,
      avg_copies: 2.1,
      category: "Trainer",
      top_archetypes: [],
      weekly_usage: [],
    };

    vi.mocked(fs.readFileSync)
      .mockReturnValueOnce(JSON.stringify(mockCard))
      .mockReturnValueOnce(JSON.stringify(MOCK_FORMATS));

    const meta = buildCardMetadata("ninja-spinner", "bosss-orders");
    expect(meta.title).toBe("Boss's Orders -- 62.4% Usage | Scout");
    expect(meta.description).toBe(
      "Boss's Orders appears in 62.4% of Ninja Spinner decks across 8 archetypes. Usage trends, synergy partners, and decklist data."
    );
  });

  it("handles NaN usage_pct gracefully", () => {
    const mockCard = {
      card_name: "Bad Card",
      slug: "bad-card",
      usage_pct: NaN,
      unique_archetypes: 0,
      avg_copies: 0,
      category: "Trainer",
      top_archetypes: [],
      weekly_usage: [],
    };

    vi.mocked(fs.readFileSync)
      .mockReturnValueOnce(JSON.stringify(mockCard))
      .mockReturnValueOnce(JSON.stringify(MOCK_FORMATS));

    const meta = buildCardMetadata("ninja-spinner", "bad-card");
    expect(meta.title).toBe("Bad Card -- 0.0% Usage | Scout");
    expect(meta.title).not.toContain("NaN");
  });

  it("handles NaN unique_archetypes gracefully", () => {
    const mockCard = {
      card_name: "Broken Card",
      slug: "broken-card",
      usage_pct: 10.0,
      unique_archetypes: NaN,
      avg_copies: 1,
      category: "Trainer",
      top_archetypes: [],
      weekly_usage: [],
    };

    vi.mocked(fs.readFileSync)
      .mockReturnValueOnce(JSON.stringify(mockCard))
      .mockReturnValueOnce(JSON.stringify(MOCK_FORMATS));

    const meta = buildCardMetadata("ninja-spinner", "broken-card");
    expect(meta.description).toContain("across 0 archetypes");
    expect(meta.description).not.toContain("NaN");
  });
});
