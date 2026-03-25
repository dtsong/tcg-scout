import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResultsTable } from "../results-table";
import type { ArchetypeResult } from "@/app/lib/types";

vi.mock("next/navigation", () => ({
  useParams: () => ({ format: "nihil-zero" }),
}));

const resultWithUrl: ArchetypeResult = {
  tournament_name: "Osaka CL Jan",
  tournament_url: "https://play.limitless.gg/tournaments/abc123",
  date: "2026-01-25",
  standing: 1,
  player_name: "Alice",
};

const resultWithoutUrl: ArchetypeResult = {
  tournament_name: "Tokyo CL Feb",
  date: "2026-02-10",
  standing: 4,
  player_name: "Bob",
};

const resultWithDecklist: ArchetypeResult = {
  tournament_name: "Berlin CL Mar",
  tournament_url: "https://play.limitless.gg/tournaments/xyz",
  date: "2026-03-15",
  standing: 2,
  player_name: "Carol",
  decklist: [
    { card_name: "Rare Candy", count: 4, category: "Trainer" },
    { card_name: "Charizard ex", count: 3, category: "Pokemon" },
  ],
};

describe("ResultsTable", () => {
  afterEach(cleanup);

  it("renders tournament name as external link when tournament_url is present", async () => {
    const user = userEvent.setup();
    render(<ResultsTable results={[resultWithUrl]} />);

    // Expand the results section
    await user.click(screen.getByRole("button", { name: /results/i }));

    const link = screen.getByRole("link", { name: "Osaka CL Jan" });
    expect(link).toHaveAttribute("href", "https://play.limitless.gg/tournaments/abc123");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("renders tournament name as plain text when tournament_url is absent", async () => {
    const user = userEvent.setup();
    render(<ResultsTable results={[resultWithoutUrl]} />);

    await user.click(screen.getByRole("button", { name: /results/i }));

    expect(screen.getByText("Tokyo CL Feb")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Tokyo CL Feb" })).toBeNull();
  });

  it("renders card names as links in expanded decklist", async () => {
    const user = userEvent.setup();
    render(<ResultsTable results={[resultWithDecklist]} />);

    await user.click(screen.getByRole("button", { name: /results/i }));
    // Expand the row to show decklist
    await user.click(screen.getByText("Carol"));

    const cardLink = screen.getByRole("link", { name: "Rare Candy" });
    expect(cardLink).toHaveAttribute("href", "/nihil-zero/cards/rare-candy");
    expect(screen.getByRole("link", { name: "Charizard ex" })).toHaveAttribute("href", "/nihil-zero/cards/charizard-ex");
  });
});
