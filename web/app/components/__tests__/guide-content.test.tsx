import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { GuideContent } from "@/app/components/guide-content";

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

const originalLocation = window.location;

describe("GuideContent", () => {
  afterEach(() => {
    cleanup();
    Object.defineProperty(window, "location", {
      value: originalLocation,
      writable: true,
      configurable: true,
    });
  });

  it("renders the page heading", () => {
    render(<GuideContent format="ninja-spinner" />);
    expect(screen.getByText("How Scout Works")).toBeInTheDocument();
  });

  it("renders all scenario cards", () => {
    render(<GuideContent format="ninja-spinner" />);
    expect(
      screen.getByText("Pick a deck for this weekend")
    ).toBeInTheDocument();
    expect(screen.getByText("Find cards that actually win")).toBeInTheDocument();
    expect(screen.getByText("Track what's changing")).toBeInTheDocument();
    expect(screen.getByText("Scout a matchup")).toBeInTheDocument();
    expect(screen.getByText("Study winning decklists")).toBeInTheDocument();
  });

  it("scenario cards link to actual pages", () => {
    render(<GuideContent format="ninja-spinner" />);
    const pickDeck = screen.getByText("Pick a deck for this weekend").closest("div")!;
    expect(within(pickDeck).getByRole("link", { name: /Dashboard/ })).toHaveAttribute("href", "/ninja-spinner");
    const findCards = screen.getByText("Find cards that actually win").closest("div")!;
    expect(within(findCards).getByRole("link", { name: /Format Edge/ })).toHaveAttribute("href", "/ninja-spinner/card-analysis");
    const trackChanges = screen.getByText("Track what's changing").closest("div")!;
    expect(within(trackChanges).getByRole("link", { name: /Trends/ })).toHaveAttribute("href", "/ninja-spinner/trends");
    const scoutMatchup = screen.getByText("Scout a matchup").closest("div")!;
    expect(within(scoutMatchup).getByRole("link", { name: /Archetypes/ })).toHaveAttribute("href", "/ninja-spinner/archetypes");
    const studyDecks = screen.getByText("Study winning decklists").closest("div")!;
    expect(within(studyDecks).getByRole("link", { name: /Champions League/ })).toHaveAttribute("href", "/ninja-spinner/champions");
  });

  it("constructs links using the provided format", () => {
    render(<GuideContent format="nihil-zero" />);
    const archetypesLink = screen.getByRole("link", { name: /Archetypes/ });
    expect(archetypesLink).toHaveAttribute("href", "/nihil-zero/archetypes");
  });

  it("renders secondary links when present", () => {
    render(<GuideContent format="ninja-spinner" />);
    const buyListLink = screen.getByRole("link", { name: /Buy List/ });
    expect(buyListLink).toHaveAttribute("href", "/ninja-spinner/buylist");
  });

  it("does not render extra links for scenarios without a secondary", () => {
    render(<GuideContent format="ninja-spinner" />);
    const card = screen.getByText("Find cards that actually win").closest("div")!;
    expect(within(card).getAllByRole("link")).toHaveLength(1);
  });

  it("renders all tool section headings", () => {
    render(<GuideContent format="ninja-spinner" />);
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
    render(<GuideContent format="ninja-spinner" />);
    expect(screen.getByText(/Tiers are based on meta share/)).toBeInTheDocument();
  });

  it("expands a collapsed section on click", async () => {
    const user = userEvent.setup();
    render(<GuideContent format="ninja-spinner" />);
    // Format Edge accordion content should be collapsed initially
    expect(
      screen.queryByText(/overrepresented in top-4 finishing decks/)
    ).not.toBeInTheDocument();
    // Click to expand - target the button specifically
    const formatEdgeButton = screen.getByRole("button", { name: /Format Edge/ });
    await user.click(formatEdgeButton);
    expect(
      screen.getByText(/overrepresented in top-4 finishing decks/)
    ).toBeInTheDocument();
  });

  it("renders intro paragraph and bullet items when section is open", () => {
    render(<GuideContent format="ninja-spinner" />);
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

  it("opens a section specified in the URL hash on mount", () => {
    Object.defineProperty(window, "location", {
      value: { hash: "#buy-list" },
      writable: true,
      configurable: true,
    });
    render(<GuideContent format="ninja-spinner" />);
    expect(
      screen.getByText(/Priority-scored card list/)
    ).toBeInTheDocument();
  });

  it("renders the glossary table", () => {
    render(<GuideContent format="ninja-spinner" />);
    expect(screen.getByText("Metric Glossary")).toBeInTheDocument();
    expect(screen.getByText("Meta share")).toBeInTheDocument();
    expect(screen.getByText("Weighted share")).toBeInTheDocument();
    expect(screen.getByText("Winning edge")).toBeInTheDocument();
    expect(screen.getByText("Top-4 edge")).toBeInTheDocument();
  });
});
