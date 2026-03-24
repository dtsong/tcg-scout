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
import { getMeta, getTrends, getArchetypeSlugs, getFormats, getFormatName, getCardAnalysis, getTechForecast, getMetaReport, getMetaEvolution } from "../data";

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fs.existsSync).mockReturnValue(true);
});

describe("getFormats", () => {
  it("returns expected FormatInfo array", () => {
    const mockFormats = [
      {
        slug: "nihil-zero",
        name: "Nihil Zero",
        name_en: "Perfect Order",
        description: "Test format",
        dataset_start: "2026-01-23",
        dataset_end: "2026-03-13",
        status: "active",
        tournament_count: 100,
        deck_count: 500,
      },
    ];

    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(mockFormats));

    const result = getFormats();
    expect(result).toHaveLength(1);
    expect(result[0].slug).toBe("nihil-zero");
    expect(result[0].status).toBe("active");
  });
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

    const result = getMeta("nihil-zero");
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

    const result = getTrends("nihil-zero");
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

    const result = getTrends("nihil-zero");
    expect(result.surging).toHaveLength(1);
    expect(result.surging[0].card_name).toBe("Iono");
    expect(result.declining).toHaveLength(0);
  });
});

describe("getArchetypeSlugs", () => {
  it("returns an array of slug strings from json filenames", () => {
    // readdirSync without options returns string[], but the mock type is broader
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (vi.mocked(fs.readdirSync) as any).mockReturnValue([
      "charizard-ex.json",
      "lugia-vstar.json",
      "gardevoir-ex.json",
    ]);

    const result = getArchetypeSlugs("nihil-zero");
    expect(result).toEqual(["charizard-ex", "lugia-vstar", "gardevoir-ex"]);
  });

  it("filters out non-json files", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (vi.mocked(fs.readdirSync) as any).mockReturnValue([
      "charizard-ex.json",
      ".DS_Store",
      "readme.txt",
    ]);

    const result = getArchetypeSlugs("nihil-zero");
    expect(result).toEqual(["charizard-ex"]);
  });
});

describe("getCardAnalysis", () => {
  it("returns null when file does not exist", () => {
    vi.mocked(fs.readFileSync).mockImplementation(() => {
      throw Object.assign(new Error("ENOENT"), { code: "ENOENT" });
    });
    expect(getCardAnalysis("test-format")).toBeNull();
  });
});

describe("getTechForecast", () => {
  it("returns parsed TechForecast data", () => {
    const mockForecast = {
      generated_at: "2026-03-20T00:00:00",
      cards: [
        {
          card_name: "Boss's Orders",
          current_adoption_pct: 34.2,
          current_avg_copies: 1.8,
          trend_direction: "rising",
          trend_delta: 8.1,
          weekly_data: [
            { week: "2026-03-10", adoption_pct: 26.1, avg_copies: 1.6, deck_count: 12, total_decks: 46 },
            { week: "2026-03-17", adoption_pct: 34.2, avg_copies: 1.8, deck_count: 18, total_decks: 52 },
          ],
          top_archetypes: [
            { archetype: "Dragapult ex", inclusion_pct: 85.0, avg_copies: 2.1 },
          ],
        },
      ],
    };

    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(mockForecast));

    const result = getTechForecast("nihil-zero");
    expect(result).not.toBeNull();
    expect(result!.cards).toHaveLength(1);
    expect(result!.cards[0].card_name).toBe("Boss's Orders");
    expect(result!.cards[0].trend_direction).toBe("rising");
    expect(result!.cards[0].weekly_data).toHaveLength(2);
    expect(result!.cards[0].top_archetypes).toHaveLength(1);
  });

  it("returns null when file does not exist", () => {
    vi.mocked(fs.readFileSync).mockImplementation(() => {
      throw Object.assign(new Error("ENOENT"), { code: "ENOENT" });
    });
    expect(getTechForecast("test-format")).toBeNull();
  });
});

describe("getMetaReport", () => {
  it("returns parsed MetaReport when file exists", () => {
    const mockReport = {
      format: "nihil-zero",
      generated_at: "2026-03-19T00:00:00Z",
      data_hash: "abc123",
      sections: [
        {
          id: "meta-at-a-glance",
          title: "Meta at a Glance",
          content: "The meta is balanced.",
          highlights: ["Key point"],
        },
      ],
    };
    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(mockReport));
    const result = getMetaReport("nihil-zero");
    expect(result).not.toBeNull();
    expect(result!.format).toBe("nihil-zero");
    expect(result!.data_hash).toBe("abc123");
    expect(result!.sections).toHaveLength(1);
    expect(result!.sections[0].id).toBe("meta-at-a-glance");
  });

  it("returns null when report file does not exist", () => {
    vi.mocked(fs.readFileSync).mockImplementation(() => {
      throw Object.assign(new Error("ENOENT"), { code: "ENOENT" });
    });
    expect(getMetaReport("nihil-zero")).toBeNull();
  });

  it("returns null when report file has invalid JSON", () => {
    vi.mocked(fs.readFileSync).mockReturnValue("not valid json{{{");
    expect(getMetaReport("nihil-zero")).toBeNull();
  });
});

describe("getMetaEvolution", () => {
  it("returns new object format as-is", () => {
    const mockData = {
      highlights: [{ card: "Iono", archetype: "Charizard", direction: "adopted", from_pct: 10, to_pct: 60, delta: 50, week: "2026-03-16" }],
      movements: [
        { card: "Iono", archetype: "Charizard", direction: "adopted", from_pct: 10, to_pct: 60, delta: 50, week: "2026-03-16" },
        { card: "Arven", archetype: "Charizard", direction: "dropped", from_pct: 80, to_pct: 10, delta: 70, week: "2026-03-16" },
      ],
    };
    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(mockData));
    const result = getMetaEvolution("ninja-spinner");
    expect(result.highlights).toHaveLength(1);
    expect(result.movements).toHaveLength(2);
  });

  it("wraps legacy bare-array format", () => {
    const mockArray = [
      { card: "Iono", archetype: "Charizard", direction: "adopted", from_pct: 10, to_pct: 60, delta: 50, week: "2026-03-16" },
    ];
    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(mockArray));
    const result = getMetaEvolution("ninja-spinner");
    expect(result.highlights).toEqual(mockArray);
    expect(result.movements).toEqual(mockArray);
  });

  it("returns empty when file not found", () => {
    vi.mocked(fs.readFileSync).mockImplementation(() => {
      const err = new Error("ENOENT") as NodeJS.ErrnoException;
      err.code = "ENOENT";
      throw err;
    });
    const result = getMetaEvolution("ninja-spinner");
    expect(result.highlights).toEqual([]);
    expect(result.movements).toEqual([]);
  });

  it("throws on non-ENOENT errors", () => {
    vi.mocked(fs.readFileSync).mockReturnValue("not valid json{{{");
    expect(() => getMetaEvolution("ninja-spinner")).toThrow();
  });
});

describe("getFormatName", () => {
  const mockFormats = [
    {
      slug: "nihil-zero",
      name: "ニヒルゼロ",
      name_en: "Perfect Order",
      description: "Test",
      dataset_start: "2026-01-23",
      dataset_end: "2026-03-13",
      status: "active",
    },
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

  it("returns name_en when format slug matches", () => {
    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(mockFormats));
    expect(getFormatName("nihil-zero")).toBe("Perfect Order");
  });

  it("returns name_en for a different matching slug", () => {
    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(mockFormats));
    expect(getFormatName("ninja-spinner")).toBe("Ninja Spinner");
  });

  it("throws when format slug is not found", () => {
    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(mockFormats));
    expect(() => getFormatName("unknown-format")).toThrow('format "unknown-format" not found');
  });

  it("falls back to raw slug when name_en is empty string", () => {
    const formatsWithEmpty = [
      { ...mockFormats[0], name_en: "" },
    ];
    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(formatsWithEmpty));
    expect(getFormatName("nihil-zero")).toBe("nihil-zero");
  });
});
