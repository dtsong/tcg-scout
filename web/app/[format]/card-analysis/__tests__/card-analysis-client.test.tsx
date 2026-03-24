import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CardAnalysisClient } from "../card-analysis-client";
import type { CardAnalysisData } from "@/app/lib/types";

const mockData: CardAnalysisData = {
  cards: [
    {
      card_name: "Boss's Orders",
      category: "Trainer",
      archetypes: [
        { archetype: "Charizard Pidgeot", slug: "charizard-pidgeot", tier: "S", delta_vs_field: 15.0, top4_inclusion_pct: 100, field_inclusion_pct: 85, avg_copies: 2.8, top4_sample_size: 10, confidence: 1.0 },
        { archetype: "Lugia Archeops", slug: "lugia-archeops", tier: "A", delta_vs_field: 8.0, top4_inclusion_pct: 90, field_inclusion_pct: 82, avg_copies: 2.5, top4_sample_size: 6, confidence: 0.6 },
      ],
      avg_delta: 11.5,
      weighted_impact: 12.8,
      confidence: 0.6,
      archetype_count: 2,
      max_delta: 15.0,
      best_archetype: "Charizard Pidgeot",
    },
    {
      card_name: "Charizard ex",
      category: "Pokemon",
      archetypes: [
        { archetype: "Charizard Pidgeot", slug: "charizard-pidgeot", tier: "S", delta_vs_field: 20.0, top4_inclusion_pct: 100, field_inclusion_pct: 80, avg_copies: 3, top4_sample_size: 10, confidence: 1.0 },
      ],
      avg_delta: 20.0,
      weighted_impact: 20.0,
      confidence: 1.0,
      archetype_count: 1,
      max_delta: 20.0,
      best_archetype: "Charizard Pidgeot",
    },
    {
      card_name: "Basic Fire Energy",
      category: "Energy",
      archetypes: [
        { archetype: "Charizard Pidgeot", slug: "charizard-pidgeot", tier: "S", delta_vs_field: 5.0, top4_inclusion_pct: 100, field_inclusion_pct: 95, avg_copies: 8, top4_sample_size: 10, confidence: 1.0 },
      ],
      avg_delta: 5.0,
      weighted_impact: 5.0,
      confidence: 1.0,
      archetype_count: 1,
      max_delta: 5.0,
      best_archetype: "Charizard Pidgeot",
    },
  ],
  generated_at: "2026-03-19T12:00:00",
};

describe("CardAnalysisClient", () => {
  afterEach(cleanup);

  it("renders all cards", () => {
    render(<CardAnalysisClient data={mockData} format="nihil-zero" />);
    expect(screen.getAllByText("Boss's Orders").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Charizard ex").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Basic Fire Energy").length).toBeGreaterThanOrEqual(1);
  });

  it("filters by category", async () => {
    const user = userEvent.setup();
    render(<CardAnalysisClient data={mockData} format="nihil-zero" />);
    await user.click(screen.getByRole("button", { name: "Pokemon" }));
    // After filtering to Pokemon, table should only show Charizard ex
    // Featured strip is unfiltered, so Boss's Orders may still appear there
    const rows = screen.getAllByTestId("card-row");
    expect(rows.length).toBe(1);
    expect(rows[0]).toHaveTextContent("Charizard ex");
  });

  it("shows card count", () => {
    render(<CardAnalysisClient data={mockData} format="nihil-zero" />);
    expect(screen.getByText(/3 cards/)).toBeInTheDocument();
  });

  it("renders page title as Format Edge", () => {
    const empty: CardAnalysisData = { cards: [], generated_at: "" };
    render(<CardAnalysisClient data={empty} format="nihil-zero" />);
    expect(screen.getByText("Format Edge")).toBeInTheDocument();
  });

  it("renders card names as links", () => {
    render(<CardAnalysisClient data={mockData} format="nihil-zero" />);
    const link = screen.getByRole("link", { name: "Charizard ex" });
    expect(link).toHaveAttribute("href", "/nihil-zero/cards/charizard-ex");
  });

  it("default sort surfaces highest weighted_impact first", () => {
    render(<CardAnalysisClient data={mockData} format="nihil-zero" />);
    const rows = screen.getAllByTestId("card-row");
    expect(rows[0]).toHaveTextContent("Charizard ex");
  });

  it("renders featured cards strip for high-impact cards", () => {
    render(<CardAnalysisClient data={mockData} format="nihil-zero" />);
    expect(screen.getByText("Top Impact Cards")).toBeInTheDocument();
  });

  it("excludes low-confidence and negative-impact cards from featured strip", () => {
    const dataWithLowConfidence: CardAnalysisData = {
      cards: [
        {
          card_name: "High Impact Card",
          category: "Trainer",
          archetypes: [
            { archetype: "TopDeck", slug: "topdeck", tier: "S", delta_vs_field: 20.0, top4_inclusion_pct: 100, field_inclusion_pct: 80, avg_copies: 3, top4_sample_size: 10, confidence: 1.0 },
          ],
          avg_delta: 20.0,
          weighted_impact: 20.0,
          confidence: 1.0,
          archetype_count: 1,
          max_delta: 20.0,
          best_archetype: "TopDeck",
        },
        {
          card_name: "Low Confidence Card",
          category: "Trainer",
          archetypes: [
            { archetype: "RogueDeck", slug: "roguedeck", tier: "Rogue", delta_vs_field: 15.0, top4_inclusion_pct: 80, field_inclusion_pct: 65, avg_copies: 2, top4_sample_size: 3, confidence: 0.3 },
          ],
          avg_delta: 15.0,
          weighted_impact: 15.0,
          confidence: 0.3,
          archetype_count: 1,
          max_delta: 15.0,
          best_archetype: "RogueDeck",
        },
        {
          card_name: "Negative Impact Card",
          category: "Pokemon",
          archetypes: [
            { archetype: "TopDeck", slug: "topdeck", tier: "S", delta_vs_field: -5.0, top4_inclusion_pct: 40, field_inclusion_pct: 45, avg_copies: 1, top4_sample_size: 10, confidence: 1.0 },
          ],
          avg_delta: -5.0,
          weighted_impact: -5.0,
          confidence: 1.0,
          archetype_count: 1,
          max_delta: -5.0,
          best_archetype: "TopDeck",
        },
      ],
      generated_at: "2026-03-19T12:00:00",
    };
    render(<CardAnalysisClient data={dataWithLowConfidence} format="nihil-zero" />);
    expect(screen.getByText("Top Impact Cards")).toBeInTheDocument();
    // Only "High Impact Card" should appear in the featured strip
    // The strip has 1 featured card link, the table has 3 card-row entries
    const rows = screen.getAllByTestId("card-row");
    expect(rows.length).toBe(3); // All cards show in table

    // Featured strip links go to /format/cards/slug — count those specific links
    const allLinks = screen.getAllByRole("link");
    const cardPageLinks = allLinks.filter((link) => link.getAttribute("href")?.includes("/cards/"));
    // 3 table links + 1 featured link = 4 total card page links
    // "High Impact Card" should appear twice (strip + table), others only once (table)
    expect(screen.getAllByText("High Impact Card").length).toBe(2);
    expect(screen.getAllByText("Low Confidence Card").length).toBe(1);
    expect(screen.getAllByText("Negative Impact Card").length).toBe(1);
  });

  it("renders archetype breakdown with confidence indicators on expand", async () => {
    const user = userEvent.setup();
    render(<CardAnalysisClient data={mockData} format="nihil-zero" />);
    const rows = screen.getAllByTestId("card-row");
    // Click the button inside the first row to expand
    const button = rows[0].querySelector("button")!;
    await user.click(button);
    const breakdown = screen.getByTestId("archetype-breakdown");
    expect(breakdown).toBeInTheDocument();
    expect(screen.getByText("Charizard Pidgeot")).toBeInTheDocument();
  });
});
