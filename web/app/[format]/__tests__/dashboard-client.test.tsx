import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { DashboardClient } from "../dashboard-client";
import type {
  MetaData,
  TrendsData,
  WinningEdgeCard,
  AceSpec,
  ArchetypeSummary,
} from "@/app/lib/types";

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

vi.mock("@/app/components/welcome-guide", () => ({
  WelcomeGuide: () => <div data-testid="welcome-guide">WelcomeGuide</div>,
}));

vi.mock("@/app/components/meta-timeline", () => ({
  MetaTimeline: () => <div data-testid="meta-timeline">MetaTimeline</div>,
}));

vi.mock("@/app/components/stat-card", () => ({
  StatCard: ({ label, value }: { label: string; value: string }) => (
    <div data-testid="stat-card">
      {label}: {value}
    </div>
  ),
}));

vi.mock("@/app/components/tier-badge", () => ({
  TierBadge: ({ tier }: { tier: string }) => (
    <span data-testid="tier-badge">{tier}</span>
  ),
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

const sArchetype = makeArchetype({
  archetype: "Dragapult ex",
  slug: "dragapult-ex",
  meta_share: 12.5,
  deck_count: 150,
  tier: "S",
});

const aArchetype = makeArchetype({
  archetype: "Charizard Pidgeot",
  slug: "charizard-pidgeot",
  meta_share: 8.3,
  deck_count: 95,
  tier: "A",
});

const bArchetype = makeArchetype({
  archetype: "Raging Bolt",
  slug: "raging-bolt",
  meta_share: 4.1,
  deck_count: 45,
  tier: "B",
});

const rogueArchetype = makeArchetype({
  archetype: "Banette ex",
  slug: "banette-ex",
  meta_share: 0.5,
  deck_count: 5,
  tier: "Rogue",
});

const baseMeta: MetaData = {
  generated_at: "2026-03-24T00:00:00Z",
  tournament_count: 430,
  deck_count: 5000,
  date_range: { start: "2025-10-01", end: "2026-03-23" },
  rotation_date: "2026-07-01",
  tier_thresholds: { S: 10, A: 5, B: 2 },
  archetypes: [sArchetype, aArchetype, bArchetype, rogueArchetype],
  format: { slug: "ninja-spinner", name: "Ninja Spinner", name_en: "Ninja Spinner" },
};

const baseTrends: TrendsData = {
  midpoint: "2026-02-15",
  early_decks: 2000,
  late_decks: 3000,
  surging: [
    { card_name: "Night Stretcher", early_count: 100, late_count: 300, early_pct: 5, late_pct: 10, delta: 5.0 },
    { card_name: "Buddy-Buddy Poffin", early_count: 200, late_count: 500, early_pct: 10, late_pct: 16.7, delta: 6.7 },
  ],
  declining: [
    { card_name: "Nest Ball", early_count: 400, late_count: 200, early_pct: 20, late_pct: 6.7, delta: -13.3 },
  ],
};

const baseWinningEdge: WinningEdgeCard[] = [
  { card_name: "Prime Catcher", field_pct: 30, win_pct: 55, edge: 25.0, winner_decks: 50, field_decks: 500 },
];

const baseAceSpecs: AceSpec[] = [
  { card_name: "Hero's Cape", deck_count: 800, usage_pct: 16.0 },
  { card_name: "Prime Catcher", deck_count: 600, usage_pct: 12.0 },
];

// --- Tests ---

describe("DashboardClient", () => {
  afterEach(cleanup);

  function renderDashboard(overrides: Partial<Parameters<typeof DashboardClient>[0]> = {}) {
    return render(
      <DashboardClient
        format="ninja-spinner"
        meta={baseMeta}
        trends={baseTrends}
        winningEdge={baseWinningEdge}
        aceSpecs={baseAceSpecs}
        {...overrides}
      />,
    );
  }

  it("renders tier sections with S, A, and B archetypes", () => {
    renderDashboard();
    const tierSection = screen.getByTestId("tier-section");
    expect(tierSection).toBeInTheDocument();

    const tierBadges = screen.getAllByTestId("tier-badge");
    const tierTexts = tierBadges.map((el) => el.textContent);
    expect(tierTexts).toContain("S");
    expect(tierTexts).toContain("A");
    expect(tierTexts).toContain("B");
  });

  it("excludes Rogue-tier archetypes from the tier list preview", () => {
    renderDashboard();
    expect(screen.queryByText("Banette ex")).not.toBeInTheDocument();
  });

  it("displays archetype names in the tier list", () => {
    renderDashboard();
    expect(screen.getByText("Dragapult ex")).toBeInTheDocument();
    expect(screen.getByText("Charizard Pidgeot")).toBeInTheDocument();
    expect(screen.getByText("Raging Bolt")).toBeInTheDocument();
  });

  it("displays meta share percentages", () => {
    renderDashboard();
    const shares = screen.getAllByTestId("meta-share");
    const shareTexts = shares.map((el) => el.textContent);
    expect(shareTexts).toContain("12.5%");
    expect(shareTexts).toContain("8.3%");
    expect(shareTexts).toContain("4.1%");
  });

  it("renders archetype links pointing to detail pages", () => {
    renderDashboard();
    const links = screen.getAllByTestId("archetype-link");
    const hrefs = links.map((el) => el.getAttribute("href"));
    expect(hrefs).toContain("/ninja-spinner/archetypes/dragapult-ex");
    expect(hrefs).toContain("/ninja-spinner/archetypes/charizard-pidgeot");
    expect(hrefs).toContain("/ninja-spinner/archetypes/raging-bolt");
  });

  it("displays deck counts for archetypes", () => {
    renderDashboard();
    expect(screen.getByText("150")).toBeInTheDocument();
    expect(screen.getByText("95")).toBeInTheDocument();
    expect(screen.getByText("45")).toBeInTheDocument();
  });

  it("shows empty tier list when no S/A/B archetypes exist", () => {
    const emptyMeta: MetaData = {
      ...baseMeta,
      archetypes: [rogueArchetype],
    };
    renderDashboard({ meta: emptyMeta });

    const tierSection = screen.getByTestId("tier-section");
    expect(tierSection).toBeInTheDocument();
    // Table exists but has no archetype rows
    expect(screen.queryAllByTestId("archetype-link")).toHaveLength(0);
  });

  it("renders surging and declining card names in the insights grid", () => {
    renderDashboard();
    expect(screen.getByText("Night Stretcher")).toBeInTheDocument();
    expect(screen.getByText("Buddy-Buddy Poffin")).toBeInTheDocument();
    expect(screen.getByText("Nest Ball")).toBeInTheDocument();
  });

  it("renders tournament count and deck count stats", () => {
    renderDashboard();
    expect(screen.getByText("430")).toBeInTheDocument();
    expect(screen.getByText("5,000")).toBeInTheDocument();
  });
});
