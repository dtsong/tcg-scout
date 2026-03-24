import { describe, it, expect, vi, afterEach } from "vitest";
import { formatPlacement, formatPct, daysUntil, cn, slugify, effectiveImpact, computeCrossMetaStaples } from "../utils";
import type { CardAnalysisEntry } from "../types";

describe("formatPlacement", () => {
  it("returns 1st for 1", () => {
    expect(formatPlacement(1)).toBe("1st");
  });

  it("returns 2nd for 2", () => {
    expect(formatPlacement(2)).toBe("2nd");
  });

  it("returns 3rd for 3", () => {
    expect(formatPlacement(3)).toBe("3rd");
  });

  it("returns 4th for 4", () => {
    expect(formatPlacement(4)).toBe("4th");
  });

  it("returns 11th for 11 (teen exception)", () => {
    expect(formatPlacement(11)).toBe("11th");
  });

  it("returns 21st for 21", () => {
    expect(formatPlacement(21)).toBe("21st");
  });

  it("returns em dash for null", () => {
    expect(formatPlacement(null)).toBe("—");
  });
});

describe("formatPct", () => {
  it("formats 9.0 as 9.0%", () => {
    expect(formatPct(9.0)).toBe("9.0%");
  });

  it("formats 15.5 as 15.5%", () => {
    expect(formatPct(15.5)).toBe("15.5%");
  });

  it("formats 0 as 0.0%", () => {
    expect(formatPct(0)).toBe("0.0%");
  });
});

describe("daysUntil", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns correct number of days until a future date", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
    expect(daysUntil("2026-01-11")).toBe(10);
  });

  it("returns negative days for a past date", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-11T00:00:00Z"));
    expect(daysUntil("2026-01-01")).toBeLessThan(0);
  });
});

describe("slugify", () => {
  it.each([
    ["Charizard ex", "charizard-ex"],
    ["Boss's Orders", "boss-s-orders"],
    ["raging-bolt", "raging-bolt"],
    ["Porygon-Z Box!", "porygon-z-box"],
    [" -Foo- ", "foo"],
  ])("slugifies %j to %j", (input, expected) => {
    expect(slugify(input)).toBe(expected);
  });
});

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("handles conditional classes", () => {
    expect(cn("base", false && "hidden", "visible")).toBe("base visible");
  });

  it("deduplicates tailwind classes", () => {
    const result = cn("p-4", "p-2");
    expect(result).toBe("p-2");
  });
});

function makeCard(overrides: Partial<CardAnalysisEntry> & { card_name: string }): CardAnalysisEntry {
  return {
    category: "Trainer",
    archetypes: [],
    avg_delta: 0,
    weighted_impact: 0,
    confidence: 1.0,
    archetype_count: 0,
    max_delta: 0,
    best_archetype: "",
    ...overrides,
  };
}

function makeArchetype(tier: string, delta: number) {
  return { archetype: `${tier}Deck`, slug: `${tier.toLowerCase()}-deck`, tier: tier as "S" | "A" | "B" | "C" | "Rogue", delta_vs_field: delta, top4_inclusion_pct: 80, field_inclusion_pct: 60, avg_copies: 2, top4_sample_size: 10, confidence: 1.0 };
}

describe("effectiveImpact", () => {
  it("returns weighted_impact when present", () => {
    const card = makeCard({ card_name: "A", weighted_impact: 12.5, avg_delta: 8.0 });
    expect(effectiveImpact(card)).toBe(12.5);
  });

  it("falls back to avg_delta when weighted_impact is undefined", () => {
    const card = makeCard({ card_name: "A", avg_delta: 8.0 });
    delete (card as unknown as Record<string, unknown>).weighted_impact;
    expect(effectiveImpact(card)).toBe(8.0);
  });

  it("returns weighted_impact of 0 without falling back", () => {
    const card = makeCard({ card_name: "A", weighted_impact: 0, avg_delta: 5.0 });
    expect(effectiveImpact(card)).toBe(0);
  });
});

describe("computeCrossMetaStaples", () => {
  it("includes cards with 3+ S/A/B archetypes with positive delta", () => {
    const cards = [
      makeCard({
        card_name: "Staple Card",
        weighted_impact: 10,
        archetypes: [makeArchetype("S", 5), makeArchetype("A", 3), makeArchetype("B", 2)],
      }),
    ];
    const result = computeCrossMetaStaples(cards);
    expect(result).toHaveLength(1);
    expect(result[0].card_name).toBe("Staple Card");
    expect(result[0].tiered_archetype_count).toBe(3);
  });

  it("excludes cards with fewer than 3 qualifying archetypes", () => {
    const cards = [
      makeCard({
        card_name: "Narrow Card",
        weighted_impact: 15,
        archetypes: [makeArchetype("S", 5), makeArchetype("A", 3)],
      }),
    ];
    const result = computeCrossMetaStaples(cards);
    expect(result).toHaveLength(0);
  });

  it("excludes C/Rogue tiers from archetype count", () => {
    const cards = [
      makeCard({
        card_name: "Wide But Low",
        weighted_impact: 5,
        archetypes: [makeArchetype("S", 5), makeArchetype("A", 3), makeArchetype("C", 4), makeArchetype("Rogue", 6)],
      }),
    ];
    const result = computeCrossMetaStaples(cards);
    // Only S and A count → 2 < 3, excluded
    expect(result).toHaveLength(0);
  });

  it("excludes archetypes with negative delta even if S/A/B tier", () => {
    const cards = [
      makeCard({
        card_name: "Mixed Card",
        weighted_impact: 3,
        archetypes: [makeArchetype("S", 5), makeArchetype("A", -2), makeArchetype("B", 1), makeArchetype("S", 3)],
      }),
    ];
    const result = computeCrossMetaStaples(cards);
    // S(+5), A(-2 excluded), B(+1), S(+3) → 3 qualifying → included
    expect(result).toHaveLength(1);
    expect(result[0].tiered_archetype_count).toBe(3);
  });

  it("sorts by tiered_archetype_count desc, then weighted_impact desc", () => {
    const cards = [
      makeCard({
        card_name: "Card A",
        weighted_impact: 20,
        archetypes: [makeArchetype("S", 5), makeArchetype("A", 3), makeArchetype("B", 2)],
      }),
      makeCard({
        card_name: "Card B",
        weighted_impact: 10,
        archetypes: [makeArchetype("S", 5), makeArchetype("A", 3), makeArchetype("B", 2), makeArchetype("S", 1)],
      }),
    ];
    const result = computeCrossMetaStaples(cards);
    // Card B has 4 archetypes, Card A has 3 → B first
    expect(result[0].card_name).toBe("Card B");
    expect(result[1].card_name).toBe("Card A");
  });

  it("limits results to 5 by default", () => {
    const cards = Array.from({ length: 10 }, (_, i) =>
      makeCard({
        card_name: `Card ${i}`,
        weighted_impact: 10 - i,
        archetypes: [makeArchetype("S", 5), makeArchetype("A", 3), makeArchetype("B", 2)],
      })
    );
    const result = computeCrossMetaStaples(cards);
    expect(result).toHaveLength(5);
  });

  it("excludes cards with negative weighted_impact", () => {
    const cards = [
      makeCard({
        card_name: "Net Negative Card",
        weighted_impact: -2,
        archetypes: [makeArchetype("S", 5), makeArchetype("A", 3), makeArchetype("B", 1)],
      }),
    ];
    const result = computeCrossMetaStaples(cards);
    expect(result).toHaveLength(0);
  });

  it("returns empty array for empty input", () => {
    expect(computeCrossMetaStaples([])).toEqual([]);
  });
});
