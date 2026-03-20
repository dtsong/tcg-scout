import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResultsTable } from "../results-table";
import type { ArchetypeResult } from "@/app/lib/types";

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
});
