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
        { archetype: "Charizard Pidgeot", slug: "charizard-pidgeot", tier: "S", delta_vs_field: 15.0, top4_inclusion_pct: 100, field_inclusion_pct: 85, avg_copies: 2.8, top4_sample_size: 10 },
        { archetype: "Lugia Archeops", slug: "lugia-archeops", tier: "A", delta_vs_field: 8.0, top4_inclusion_pct: 90, field_inclusion_pct: 82, avg_copies: 2.5, top4_sample_size: 6 },
      ],
      avg_delta: 11.5,
      archetype_count: 2,
      max_delta: 15.0,
      best_archetype: "Charizard Pidgeot",
    },
    {
      card_name: "Charizard ex",
      category: "Pokemon",
      archetypes: [
        { archetype: "Charizard Pidgeot", slug: "charizard-pidgeot", tier: "S", delta_vs_field: 20.0, top4_inclusion_pct: 100, field_inclusion_pct: 80, avg_copies: 3, top4_sample_size: 10 },
      ],
      avg_delta: 20.0,
      archetype_count: 1,
      max_delta: 20.0,
      best_archetype: "Charizard Pidgeot",
    },
    {
      card_name: "Basic Fire Energy",
      category: "Energy",
      archetypes: [
        { archetype: "Charizard Pidgeot", slug: "charizard-pidgeot", tier: "S", delta_vs_field: 5.0, top4_inclusion_pct: 100, field_inclusion_pct: 95, avg_copies: 8, top4_sample_size: 10 },
      ],
      avg_delta: 5.0,
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
    expect(screen.getByText("Boss's Orders")).toBeInTheDocument();
    expect(screen.getByText("Charizard ex")).toBeInTheDocument();
    expect(screen.getByText("Basic Fire Energy")).toBeInTheDocument();
  });

  it("filters by category", async () => {
    const user = userEvent.setup();
    render(<CardAnalysisClient data={mockData} format="nihil-zero" />);
    await user.click(screen.getByRole("button", { name: "Pokemon" }));
    expect(screen.getByText("Charizard ex")).toBeInTheDocument();
    expect(screen.queryByText("Boss's Orders")).not.toBeInTheDocument();
    expect(screen.queryByText("Basic Fire Energy")).not.toBeInTheDocument();
  });

  it("shows card count", () => {
    render(<CardAnalysisClient data={mockData} format="nihil-zero" />);
    expect(screen.getByText(/3 cards/)).toBeInTheDocument();
  });

  it("renders empty state gracefully", () => {
    const empty: CardAnalysisData = { cards: [], generated_at: "" };
    render(<CardAnalysisClient data={empty} format="nihil-zero" />);
    expect(screen.getByText("Card Analysis")).toBeInTheDocument();
  });
});
