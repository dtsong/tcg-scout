import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ArchetypeDetailClient } from "../archetype-detail-client";
import type { ArchetypeDetail, MatchupMatrixData } from "@/app/lib/types";

// Mock next/navigation
const mockReplace = vi.fn();
let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams,
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => "/ninja-spinner/archetypes/dragapult-dusknoir",
  useParams: () => ({ format: "ninja-spinner", slug: "dragapult-dusknoir" }),
}));

// Mock heavy components to keep tests fast
vi.mock("@/app/components/performance-trendline", () => ({
  PerformanceTrendline: () => <div data-testid="trendline">Trendline</div>,
}));
vi.mock("@/app/components/variant-breakdown", () => ({
  VariantBreakdown: () => <div data-testid="variants">Variants</div>,
}));
vi.mock("@/app/components/archetype-radar", () => ({
  ArchetypeRadar: () => <div data-testid="radar">Radar</div>,
}));
vi.mock("@/app/components/key-matchups", () => ({
  KeyMatchups: () => <div data-testid="matchups">Matchups</div>,
}));
vi.mock("@/app/components/evolution-timeline", () => ({
  EvolutionTimeline: () => <div data-testid="evolution">Evolution</div>,
}));
vi.mock("@/app/components/top4-card-stats", () => ({
  Top4CardStats: () => <div data-testid="top4">Top4</div>,
}));
vi.mock("../results-table", () => ({
  ResultsTable: () => <div data-testid="results-table">Results</div>,
}));

const baseArch: ArchetypeDetail = {
  archetype: "Dragapult Dusknoir",
  slug: "dragapult-dusknoir",
  tier: "S",
  meta_share: 16.0,
  weighted_share: 16.2,
  deck_count: 24,
  best_placement: 1,
  sprite_filenames: [],
  core_cards: [{ card_name: "Dragapult ex", avg_copies: 3, inclusion_pct: 98, category: "Pokemon", decks_with: 23 }],
  all_cards: [
    { card_name: "Dragapult ex", avg_copies: 3, inclusion_pct: 98, category: "Pokemon", decks_with: 23 },
    { card_name: "Boss's Orders", avg_copies: 2, inclusion_pct: 90, category: "Trainer", decks_with: 22 },
    { card_name: "Basic Fire Energy", avg_copies: 4, inclusion_pct: 100, category: "Energy", decks_with: 24 },
  ],
  weekly_shares: [
    { week: "2026-03-01", meta_share: 0.14, deck_count: 20 },
    { week: "2026-03-08", meta_share: 0.15, deck_count: 22 },
    { week: "2026-03-15", meta_share: 0.16, deck_count: 24 },
  ],
  radar: { meta_share: 80, weighted_share: 85, consistency: 70, ceiling: 90, popularity: 75, core_density: 60 },
  variants: [
    { name: "Base", deck_count: 15, pct: 62.5 },
    { name: "Tech", deck_count: 9, pct: 37.5 },
  ],
  evolution: [{ week: "2026-03-01", adopted: [], dropped: [] }],
  results: [{ tournament_name: "Fukuoka CL", tournament_url: "fukuoka", date: "2026-03-20", standing: 1, player_name: "Player A", decklist: [] }],
  top4_card_stats: [{ card_name: "Dragapult ex", avg_copies: 3, inclusion_pct: 100, category: "Pokemon", decks_with: 4, delta_vs_field: 0.02 }],
  top4_sample_size: 4,
  top4_low_sample: true,
};

const matchupData: MatchupMatrixData = {
  archetypes: ["Dragapult Dusknoir", "Raging Bolt"],
  matrix: [[0, -0.3], [0.3, 0]],
  sample_sizes: [[0, 77], [77, 0]],
};

function renderClient(tab?: string) {
  if (tab) {
    mockSearchParams = new URLSearchParams(`tab=${tab}`);
  } else {
    mockSearchParams = new URLSearchParams();
  }
  const result = render(
    <ArchetypeDetailClient
      arch={baseArch}
      matchupData={matchupData}
      format="ninja-spinner"
      slug="dragapult-dusknoir"
      hasReport={false}
      hasOptimal60={true}
    />,
  );
  return { ...result, scope: within(result.container) };
}

describe("ArchetypeDetailClient", () => {
  beforeEach(() => {
    mockReplace.mockClear();
  });

  it("renders header with archetype name and stats", () => {
    const { scope } = renderClient();
    expect(scope.getByText("Dragapult Dusknoir")).toBeInTheDocument();
    expect(scope.getByText("16.0%")).toBeInTheDocument();
  });

  it("renders all four tab buttons", () => {
    const { scope } = renderClient();
    expect(scope.getByText("Overview")).toBeInTheDocument();
    // "Decklist" appears as both tab button and section header -- use role
    const tabButtons = scope.getAllByRole("button");
    const tabLabels = tabButtons.map((b) => b.textContent);
    expect(tabLabels).toContain("Overview");
    expect(tabLabels).toContain("Decklist");
    expect(tabLabels).toContain("Matchups");
    expect(tabLabels).toContain("Results");
  });

  it("defaults to overview tab", () => {
    const { scope } = renderClient();
    expect(scope.getByTestId("trendline")).toBeInTheDocument();
    expect(scope.getByTestId("radar")).toBeInTheDocument();
  });

  it("shows decklist tab content when tab=decklist", () => {
    const { scope } = renderClient("decklist");
    expect(scope.getByText("Pokemon")).toBeInTheDocument();
    expect(scope.getByText("Trainer")).toBeInTheDocument();
    expect(scope.getByText("Energy")).toBeInTheDocument();
    expect(scope.getByTestId("top4")).toBeInTheDocument();
  });

  it("shows matchups tab content when tab=matchups", () => {
    const { scope } = renderClient("matchups");
    expect(scope.getByTestId("matchups")).toBeInTheDocument();
  });

  it("shows results tab content when tab=results", () => {
    const { scope } = renderClient("results");
    expect(scope.getByTestId("evolution")).toBeInTheDocument();
    expect(scope.getByTestId("results-table")).toBeInTheDocument();
  });

  it("falls back to overview for invalid tab param", () => {
    const { scope } = renderClient("bogus");
    expect(scope.getByTestId("trendline")).toBeInTheDocument();
  });

  it("navigates to tab via router.replace on click", async () => {
    const { scope } = renderClient();
    const decklistTab = scope.getAllByRole("button").find((b) => b.textContent === "Decklist")!;
    await userEvent.click(decklistTab);
    expect(mockReplace).toHaveBeenCalledWith(
      "/ninja-spinner/archetypes/dragapult-dusknoir?tab=decklist",
      { scroll: false },
    );
  });

  it("removes tab param when clicking overview", async () => {
    const { scope } = renderClient("decklist");
    await userEvent.click(scope.getByText("Overview"));
    expect(mockReplace).toHaveBeenCalledWith(
      "/ninja-spinner/archetypes/dragapult-dusknoir",
      { scroll: false },
    );
  });
});
