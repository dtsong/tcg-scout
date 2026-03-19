import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Top4CardStats } from "../top4-card-stats";
import type { TopPerformerCard } from "@/app/lib/types";

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
};

describe("Top4CardStats", () => {
  afterEach(cleanup);

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
});
