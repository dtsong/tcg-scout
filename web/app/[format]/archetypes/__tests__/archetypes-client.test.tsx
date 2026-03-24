import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { ArchetypesClient } from "../archetypes-client";
import type { ArchetypeSummary } from "@/app/lib/types";

// --- Mocks ---

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...rest
  }: {
    href: string;
    children: React.ReactNode;
  }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

vi.mock("@/app/components/date-filter-provider", () => ({
  useDateFilter: () => ({
    activeWindow: "all" as const,
    customRange: undefined,
    setWindow: vi.fn(),
  }),
  fetchWindowedData: vi.fn(),
}));

vi.mock("@/app/components/date-filter", () => ({
  DateFilter: () => <div data-testid="date-filter">DateFilter</div>,
}));

vi.mock("@/app/components/tier-badge", () => ({
  TierBadge: ({ tier }: { tier: string }) => (
    <span data-testid="tier-badge">{tier}</span>
  ),
}));

vi.mock("@/app/components/sprite-row", () => ({
  SpriteRow: ({ filenames }: { filenames: string[] }) => (
    <span data-testid="sprite-row">{filenames.join(",")}</span>
  ),
}));

vi.mock("@/app/components/meta-bar-chart", () => ({
  MetaBarChart: () => <div data-testid="meta-bar-chart">MetaBarChart</div>,
}));

vi.mock("@/app/components/archetype-heat-matrix", () => ({
  ArchetypeHeatMatrix: () => <div data-testid="archetype-heat-matrix" />,
}));

vi.mock("@/app/components/matchup-heat-matrix", () => ({
  MatchupHeatMatrix: () => <div data-testid="matchup-heat-matrix" />,
}));

vi.mock("@/app/components/tooltip", () => ({
  InfoIcon: () => <span data-testid="info-icon" />,
}));

// --- Test Data ---

function makeArchetype(overrides: Partial<ArchetypeSummary>): ArchetypeSummary {
  return {
    archetype: "Unknown Deck",
    slug: "unknown-deck",
    meta_share: 5.0,
    deck_count: 20,
    best_placement: 1,
    tier: "B",
    ...overrides,
  };
}

const mockArchetypes: ArchetypeSummary[] = [
  makeArchetype({
    archetype: "Charizard Pidgeot",
    slug: "charizard-pidgeot",
    meta_share: 18.5,
    weighted_share: 22.3,
    deck_count: 150,
    best_placement: 1,
    tier: "S",
    sprite_filenames: ["charizard.png", "pidgeot.png"],
    trend: "up",
    trend_delta: 3.2,
  }),
  makeArchetype({
    archetype: "Dragapult Dusknoir",
    slug: "dragapult-dusknoir",
    meta_share: 12.0,
    weighted_share: 14.1,
    deck_count: 95,
    best_placement: 1,
    tier: "A",
    sprite_filenames: ["dragapult.png", "dusknoir.png"],
    trend: "stable",
  }),
  makeArchetype({
    archetype: "Raging Bolt",
    slug: "raging-bolt",
    meta_share: 6.0,
    deck_count: 40,
    best_placement: 3,
    tier: "B",
    sprite_filenames: ["raging-bolt.png"],
    trend: "down",
    trend_delta: -1.5,
  }),
  makeArchetype({
    archetype: "Lugia Archeops",
    slug: "lugia-archeops",
    meta_share: 3.0,
    deck_count: 18,
    best_placement: 9,
    tier: "C",
    trend: "new",
  }),
  makeArchetype({
    archetype: "Iron Thorns",
    slug: "iron-thorns",
    meta_share: 1.2,
    deck_count: 8,
    best_placement: 17,
    tier: "Rogue",
  }),
];

const defaultDateRange = { start: "2026-01-01", end: "2026-03-24" };

function renderClient(archetypes: ArchetypeSummary[] = mockArchetypes) {
  return render(
    <ArchetypesClient
      archetypes={archetypes}
      format="ninja-spinner"
      dateRange={defaultDateRange}
    />,
  );
}

// --- Tests ---

describe("ArchetypesClient", () => {
  afterEach(cleanup);

  it("renders page title", () => {
    renderClient();
    expect(screen.getByText("Archetypes")).toBeInTheDocument();
  });

  it("shows archetype count and total decklists", () => {
    renderClient();
    expect(
      screen.getByText(/5 archetypes across 311 decklists/),
    ).toBeInTheDocument();
  });

  it("renders archetype names", () => {
    renderClient();
    expect(screen.getByText("Charizard Pidgeot")).toBeInTheDocument();
    expect(screen.getByText("Dragapult Dusknoir")).toBeInTheDocument();
    expect(screen.getByText("Raging Bolt")).toBeInTheDocument();
    expect(screen.getByText("Lugia Archeops")).toBeInTheDocument();
    expect(screen.getByText("Iron Thorns")).toBeInTheDocument();
  });

  it("renders tier badges for each archetype", () => {
    renderClient();
    const badges = screen.getAllByTestId("tier-badge");
    const tierTexts = badges.map((b) => b.textContent);
    expect(tierTexts).toContain("S");
    expect(tierTexts).toContain("A");
    expect(tierTexts).toContain("B");
    expect(tierTexts).toContain("C");
    expect(tierTexts).toContain("Rogue");
  });

  it("displays meta share percentages", () => {
    renderClient();
    // Weighted share is displayed via formatPct; check the rendered text
    // Charizard has weighted_share 22.3 and meta_share 18.5
    expect(screen.getByText(/22\.3%/)).toBeInTheDocument();
    expect(screen.getByText(/18\.5%/)).toBeInTheDocument();
  });

  it("displays deck counts", () => {
    renderClient();
    expect(screen.getByText("150")).toBeInTheDocument();
    expect(screen.getByText("95")).toBeInTheDocument();
    expect(screen.getByText("40")).toBeInTheDocument();
  });

  it("renders links to archetype detail pages", () => {
    renderClient();
    const link = screen.getByText("Charizard Pidgeot").closest("a");
    expect(link).toHaveAttribute(
      "href",
      "/ninja-spinner/archetypes/charizard-pidgeot",
    );
  });

  it("renders sprite rows for archetypes with sprites", () => {
    renderClient();
    const sprites = screen.getAllByTestId("sprite-row");
    const spriteTexts = sprites.map((s) => s.textContent);
    expect(spriteTexts).toContain("charizard.png,pidgeot.png");
    expect(spriteTexts).toContain("dragapult.png,dusknoir.png");
    expect(spriteTexts).toContain("raging-bolt.png");
  });

  it("renders empty sprite row for archetypes without sprites", () => {
    renderClient();
    const sprites = screen.getAllByTestId("sprite-row");
    // Lugia Archeops and Iron Thorns have no sprite_filenames (defaults to [])
    const emptySprites = sprites.filter((s) => s.textContent === "");
    expect(emptySprites.length).toBeGreaterThanOrEqual(2);
  });

  it("renders MetaBarChart", () => {
    renderClient();
    expect(screen.getByTestId("meta-bar-chart")).toBeInTheDocument();
  });

  it("renders DateFilter", () => {
    renderClient();
    expect(screen.getByTestId("date-filter")).toBeInTheDocument();
  });

  it("shows All Archetypes tab with count", () => {
    renderClient();
    expect(screen.getByText("All Archetypes")).toBeInTheDocument();
    // The tab shows the count as a separate span
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("renders guide link", () => {
    renderClient();
    const guideLink = screen.getByText(/How this works/);
    expect(guideLink).toHaveAttribute(
      "href",
      "/ninja-spinner/guide#archetypes",
    );
  });

  it("renders empty state with zero archetypes", () => {
    renderClient([]);
    expect(
      screen.getByText(/0 archetypes across 0 decklists/),
    ).toBeInTheDocument();
    // Tab count shows 0
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("does not render matchups tab when no matchup data provided", () => {
    renderClient();
    expect(screen.queryByText("Matchups")).not.toBeInTheDocument();
  });

  it("does not render overlap tab when no overlap data provided", () => {
    renderClient();
    expect(screen.queryByText("Card Overlap")).not.toBeInTheDocument();
  });
});
