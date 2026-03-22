import { describe, it, expect, afterEach, vi, beforeEach } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Top4CardStats } from "../top4-card-stats";
import type { TopPerformerCard, CardDecklistData } from "@/app/lib/types";

function makeCard(overrides: Partial<TopPerformerCard> & { card_name: string }): TopPerformerCard {
  return {
    inclusion_pct: 80,
    avg_copies: 3,
    decks_with: 10,
    category: "Pokemon",
    delta_vs_field: 0,
    ...overrides,
  };
}

const sampleCards: TopPerformerCard[] = [
  makeCard({ card_name: "Charizard ex", category: "Pokemon", delta_vs_field: 12.5, inclusion_pct: 95, avg_copies: 3 }),
  makeCard({ card_name: "Boss's Orders", category: "Trainer", delta_vs_field: 8.0, inclusion_pct: 70, avg_copies: 2 }),
  makeCard({ card_name: "Basic Fire Energy", category: "Energy", delta_vs_field: -5.2, inclusion_pct: 60, avg_copies: 4 }),
  makeCard({ card_name: "Rare Candy", category: "Trainer", delta_vs_field: 0, inclusion_pct: 50, avg_copies: 2 }),
  makeCard({ card_name: "Pidgeot ex", category: "Pokemon", delta_vs_field: -3.1, inclusion_pct: 40, avg_copies: 2 }),
];

const defaultProps = {
  cards: sampleCards,
  sampleSize: 8,
  lowSample: false,
  deckCount: 50,
  format: "nihil-zero",
};

const mockDecklistData: CardDecklistData = {
  card_name: "Charizard ex",
  top4_results: [
    {
      archetype: "Charizard Pidgeot",
      archetype_slug: "charizard-pidgeot",
      tournament_name: "Osaka CL",
      date: "2026-03-01",
      standing: 1,
      copies: 2,
      decklist_url: "https://limitlesstcg.com/decks/list/1",
    },
    {
      archetype: "Charizard Pidgeot",
      archetype_slug: "charizard-pidgeot",
      tournament_name: "Tokyo CL",
      date: "2026-03-08",
      standing: 3,
      copies: 2,
      decklist_url: null,
    },
  ],
};

describe("Top4CardStats", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders overperformers and underperformers in correct sections", () => {
    render(<Top4CardStats {...defaultProps} />);

    expect(screen.getByText("Overperformers")).toBeInTheDocument();
    expect(screen.getByText("Underperformers")).toBeInTheDocument();

    // Overperformers: Charizard ex (+12.5), Boss's Orders (+8.0)
    expect(screen.getByText("Charizard ex")).toBeInTheDocument();
    expect(screen.getByText("Boss's Orders")).toBeInTheDocument();

    // Underperformers: Basic Fire Energy (-5.2), Pidgeot ex (-3.1)
    expect(screen.getByText("Basic Fire Energy")).toBeInTheDocument();
    expect(screen.getByText("Pidgeot ex")).toBeInTheDocument();
  });

  it("renders card names as links to card detail pages", () => {
    render(<Top4CardStats {...defaultProps} />);

    const charizardLink = screen.getByRole("link", { name: "Charizard ex" });
    expect(charizardLink).toHaveAttribute("href", "/nihil-zero/cards/charizard-ex");

    const bossLink = screen.getByRole("link", { name: "Boss's Orders" });
    expect(bossLink).toHaveAttribute("href", "/nihil-zero/cards/boss-s-orders");
  });

  it("uses format prop in card link URLs", () => {
    render(<Top4CardStats {...defaultProps} format="standard" />);

    const link = screen.getByRole("link", { name: "Charizard ex" });
    expect(link).toHaveAttribute("href", "/standard/cards/charizard-ex");
  });

  it("sorts cards by delta descending within each section", () => {
    render(<Top4CardStats {...defaultProps} />);

    const allText = document.body.textContent ?? "";
    const charizardIdx = allText.indexOf("Charizard ex");
    const bossIdx = allText.indexOf("Boss's Orders");
    const fireIdx = allText.indexOf("Basic Fire Energy");
    const pidgeotIdx = allText.indexOf("Pidgeot ex");

    // Overperformers: Charizard (+12.5) before Boss's Orders (+8.0)
    expect(charizardIdx).toBeLessThan(bossIdx);
    // Underperformers: Pidgeot (-3.1) before Fire Energy (-5.2) (less negative first)
    expect(pidgeotIdx).toBeLessThan(fireIdx);
  });

  it("filters cards by category", async () => {
    const user = userEvent.setup();
    render(<Top4CardStats {...defaultProps} />);

    await user.click(screen.getByRole("button", { name: "Pokemon" }));

    expect(screen.getByText("Charizard ex")).toBeInTheDocument();
    expect(screen.getByText("Pidgeot ex")).toBeInTheDocument();
    expect(screen.queryByText("Boss's Orders")).not.toBeInTheDocument();
    expect(screen.queryByText("Basic Fire Energy")).not.toBeInTheDocument();
    expect(screen.queryByText("Rare Candy")).not.toBeInTheDocument();
  });

  it("shows low sample warning when lowSample is true", () => {
    render(<Top4CardStats {...defaultProps} lowSample={true} />);
    expect(screen.getByText(/Low sample size/)).toBeInTheDocument();
  });

  it("hides low sample warning when lowSample is false", () => {
    render(<Top4CardStats {...defaultProps} lowSample={false} />);
    expect(screen.queryByText(/Low sample size/)).not.toBeInTheDocument();
  });

  it("shows neutral card count when cards have zero delta", () => {
    render(<Top4CardStats {...defaultProps} />);
    expect(screen.getByText(/1 cards? with no difference/)).toBeInTheDocument();
  });

  it("hides neutral message when no cards have zero delta", () => {
    const noNeutral = sampleCards.filter((c) => c.delta_vs_field !== 0);
    render(<Top4CardStats {...defaultProps} cards={noNeutral} />);
    expect(screen.queryByText(/cards? with no difference/)).not.toBeInTheDocument();
  });

  it("renders empty state without crashing", () => {
    render(<Top4CardStats {...defaultProps} cards={[]} />);
    expect(screen.getByText("Top 4 Card Analysis")).toBeInTheDocument();
    expect(screen.queryByText("Overperformers")).not.toBeInTheDocument();
    expect(screen.queryByText("Underperformers")).not.toBeInTheDocument();
  });

  it("displays sample size and deck count in description", () => {
    render(<Top4CardStats {...defaultProps} sampleSize={8} deckCount={50} />);
    expect(screen.getByText(/8 decks/)).toBeInTheDocument();
    expect(screen.getByText(/50 decks/)).toBeInTheDocument();
  });

  it("formats copies as integer when whole number", () => {
    const wholeCard = [makeCard({ card_name: "Test Card", avg_copies: 4, delta_vs_field: 5 })];
    render(<Top4CardStats {...defaultProps} cards={wholeCard} />);
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("formats copies with one decimal when fractional", () => {
    const fracCard = [makeCard({ card_name: "Test Card", avg_copies: 3.5, delta_vs_field: 5 })];
    render(<Top4CardStats {...defaultProps} cards={fracCard} />);
    expect(screen.getByText("3.5")).toBeInTheDocument();
  });

  it("has aria-expanded on card rows", () => {
    render(<Top4CardStats {...defaultProps} />);
    const buttons = screen.getAllByRole("button", { expanded: false });
    // At least the card row buttons should have aria-expanded
    expect(buttons.length).toBeGreaterThan(0);
  });

  it("expands card row on click and fetches decklist data", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockDecklistData,
    } as Response);

    render(<Top4CardStats {...defaultProps} />);

    // Find the Charizard ex row button (it's a button with aria-expanded)
    const charizardButton = screen.getByRole("button", { name: /Charizard ex/i });
    await user.click(charizardButton);

    // Should show loading then data
    await waitFor(() => {
      expect(screen.getByText("Charizard Pidgeot")).toBeInTheDocument();
    });

    expect(screen.getByText("Osaka CL")).toBeInTheDocument();
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/data/nihil-zero/card-decklists/charizard-ex.json"
    );
  });

  it("collapses expanded card on second click", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockDecklistData,
    } as Response);

    render(<Top4CardStats {...defaultProps} />);

    const charizardButton = screen.getByRole("button", { name: /Charizard ex/i });
    await user.click(charizardButton);

    await waitFor(() => {
      expect(screen.getByText("Charizard Pidgeot")).toBeInTheDocument();
    });

    // Click again to collapse
    await user.click(charizardButton);
    expect(screen.queryByText("Charizard Pidgeot")).not.toBeInTheDocument();
  });

  it("shows empty message when no decklist data available", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 404,
    } as Response);

    render(<Top4CardStats {...defaultProps} />);

    const charizardButton = screen.getByRole("button", { name: /Charizard ex/i });
    await user.click(charizardButton);

    await waitFor(() => {
      expect(screen.getByText(/No decklist data available/)).toBeInTheDocument();
    });
  });

  it("renders external link icon for decklist URLs", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockDecklistData,
    } as Response);

    render(<Top4CardStats {...defaultProps} />);

    const charizardButton = screen.getByRole("button", { name: /Charizard ex/i });
    await user.click(charizardButton);

    await waitFor(() => {
      const externalLinks = screen.getAllByTitle("View decklist on Limitless");
      expect(externalLinks.length).toBeGreaterThan(0);
      expect(externalLinks[0].closest("a")).toHaveAttribute("target", "_blank");
    });
  });
});
