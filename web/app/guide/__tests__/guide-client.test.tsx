import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { GuideClient } from "../guide-client";

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

describe("GuideClient", () => {
  afterEach(cleanup);

  it("renders the page heading", () => {
    render(<GuideClient />);
    expect(screen.getByText("How Scout Works")).toBeInTheDocument();
  });

  it("renders all scenario cards", () => {
    render(<GuideClient />);
    expect(
      screen.getByText("Pick a deck for this weekend")
    ).toBeInTheDocument();
    expect(screen.getByText("Find cards that actually win")).toBeInTheDocument();
    expect(screen.getByText("Track what's changing")).toBeInTheDocument();
    expect(screen.getByText("Scout a matchup")).toBeInTheDocument();
    expect(screen.getByText("Study winning decklists")).toBeInTheDocument();
  });

  it("scenario cards link to actual pages", () => {
    render(<GuideClient format="ninja-spinner" />);
    const dashboardLink = screen.getByRole("link", { name: /Dashboard/ });
    expect(dashboardLink).toHaveAttribute("href", "/ninja-spinner");
    const formatEdgeLink = screen.getByRole("link", { name: /Format Edge/ });
    expect(formatEdgeLink).toHaveAttribute("href", "/ninja-spinner/card-analysis");
    const trendsLink = screen.getByRole("link", { name: /Trends/ });
    expect(trendsLink).toHaveAttribute("href", "/ninja-spinner/trends");
    const archetypesLink = screen.getByRole("link", { name: /Archetypes/ });
    expect(archetypesLink).toHaveAttribute("href", "/ninja-spinner/archetypes");
    const championsLink = screen.getByRole("link", { name: /Champions League/ });
    expect(championsLink).toHaveAttribute("href", "/ninja-spinner/champions");
  });

  it("renders secondary links when present", () => {
    render(<GuideClient format="ninja-spinner" />);
    const buyListLink = screen.getByRole("link", { name: /Buy List/ });
    expect(buyListLink).toHaveAttribute("href", "/ninja-spinner/buylist");
  });

  it("renders all tool section headings", () => {
    render(<GuideClient />);
    // Use getAllByText since some names also appear in the glossary "Found on" column
    expect(screen.getAllByText("Dashboard").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Archetypes").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Format Edge").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Cards").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Buy List").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Trends").length).toBeGreaterThanOrEqual(1);
    expect(
      screen.getAllByText("Champions League").length
    ).toBeGreaterThanOrEqual(1);
  });

  it("has first section (Dashboard) open by default", () => {
    render(<GuideClient />);
    expect(screen.getByText(/Tiers are based on meta share/)).toBeInTheDocument();
  });

  it("expands a collapsed section on click", async () => {
    const user = userEvent.setup();
    render(<GuideClient />);
    // Format Edge accordion content should be collapsed initially
    expect(
      screen.queryByText(/overrepresented in top-4 finishing decks/)
    ).not.toBeInTheDocument();
    // Click to expand - target the button specifically
    const formatEdgeButton = screen
      .getAllByText("Format Edge")
      .find((el) => el.tagName === "SPAN");
    await user.click(formatEdgeButton!);
    expect(
      screen.getByText(/overrepresented in top-4 finishing decks/)
    ).toBeInTheDocument();
  });

  it("renders intro paragraph and bullet items when section is open", () => {
    render(<GuideClient />);
    // Dashboard is open by default — check intro and bullets
    expect(
      screen.getByText(
        "Overview of the current meta with tier rankings and card trends."
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(/ACE SPEC chart shows which ACE SPECs/)
    ).toBeInTheDocument();
    // Bullets render as list items
    const bullets = screen.getAllByRole("listitem");
    expect(bullets.length).toBeGreaterThanOrEqual(5);
  });

  it("renders the glossary table", () => {
    render(<GuideClient />);
    expect(screen.getByText("Metric Glossary")).toBeInTheDocument();
    expect(screen.getByText("Meta share")).toBeInTheDocument();
    expect(screen.getByText("Weighted share")).toBeInTheDocument();
    expect(screen.getByText("Winning edge")).toBeInTheDocument();
    expect(screen.getByText("Top-4 edge")).toBeInTheDocument();
  });
});
