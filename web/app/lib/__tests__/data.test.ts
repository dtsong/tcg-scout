import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("fs", () => ({
  default: {
    readFileSync: vi.fn(),
    readdirSync: vi.fn(),
  },
  readFileSync: vi.fn(),
  readdirSync: vi.fn(),
}));

import fs from "fs";
import { getMeta, getTrends, getArchetypeSlugs } from "../data";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("getMeta", () => {
  it("returns expected MetaData structure", () => {
    const mockMeta = {
      generated_at: "2026-03-15T00:00:00Z",
      tournament_count: 5,
      deck_count: 100,
      date_range: { start: "2026-03-01", end: "2026-03-15" },
      rotation_date: "2026-04-01",
      tier_thresholds: { S: 10, A: 5, B: 2 },
      archetypes: [
        {
          archetype: "Charizard ex",
          slug: "charizard-ex",
          meta_share: 15.0,
          deck_count: 15,
          best_placement: 1,
          tier: "S",
        },
      ],
    };

    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(mockMeta));

    const result = getMeta();
    expect(result.tournament_count).toBe(5);
    expect(result.deck_count).toBe(100);
    expect(result.archetypes).toHaveLength(1);
    expect(result.archetypes[0].slug).toBe("charizard-ex");
  });
});

describe("getTrends", () => {
  it("returns data as-is when in new format (surging/declining)", () => {
    const mockTrends = {
      midpoint: "2026-03-08",
      early_decks: 50,
      late_decks: 50,
      surging: [
        {
          card_name: "Rare Candy",
          early_count: 10,
          late_count: 20,
          early_pct: 20,
          late_pct: 40,
          delta: 20,
        },
      ],
      declining: [
        {
          card_name: "Boss's Orders",
          early_count: 20,
          late_count: 10,
          early_pct: 40,
          late_pct: 20,
          delta: -20,
        },
      ],
    };

    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(mockTrends));

    const result = getTrends();
    expect(result.surging).toHaveLength(1);
    expect(result.surging[0].card_name).toBe("Rare Candy");
    expect(result.declining).toHaveLength(1);
    expect(result.declining[0].card_name).toBe("Boss's Orders");
  });

  it("transforms old format (cards field) to surging/declining", () => {
    const mockOldTrends = {
      midpoint: "2026-03-08",
      early_decks: 50,
      late_decks: 50,
      cards: [
        {
          card_name: "Iono",
          early_count: 5,
          late_count: 15,
          early_pct: 10,
          late_pct: 30,
          delta: 20,
        },
      ],
    };

    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(mockOldTrends));

    const result = getTrends();
    expect(result.surging).toHaveLength(1);
    expect(result.surging[0].card_name).toBe("Iono");
    expect(result.declining).toHaveLength(0);
  });
});

describe("getArchetypeSlugs", () => {
  it("returns an array of slug strings from json filenames", () => {
    vi.mocked(fs.readdirSync).mockReturnValue([
      "charizard-ex.json" as unknown as fs.Dirent,
      "lugia-vstar.json" as unknown as fs.Dirent,
      "gardevoir-ex.json" as unknown as fs.Dirent,
    ]);

    const result = getArchetypeSlugs();
    expect(result).toEqual(["charizard-ex", "lugia-vstar", "gardevoir-ex"]);
  });

  it("filters out non-json files", () => {
    vi.mocked(fs.readdirSync).mockReturnValue([
      "charizard-ex.json" as unknown as fs.Dirent,
      ".DS_Store" as unknown as fs.Dirent,
      "readme.txt" as unknown as fs.Dirent,
    ]);

    const result = getArchetypeSlugs();
    expect(result).toEqual(["charizard-ex"]);
  });
});
