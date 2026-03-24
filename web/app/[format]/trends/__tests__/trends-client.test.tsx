import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { TrendsClient } from "../trends-client";
import type { TrendsData, TrendCard, WinningEdgeCard } from "@/app/lib/types";

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

vi.mock("recharts", () => ({
  BarChart: ({ children }: { children: React.ReactNode }) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => <div data-testid="bar" />,
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  Tooltip: () => <div data-testid="tooltip" />,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="responsive-container">{children}</div>,
  Legend: () => <div data-testid="legend" />,
}));

vi.mock("lucide-react", () => ({
  TrendingUp: () => <span data-testid="trending-up-icon" />,
  TrendingDown: () => <span data-testid="trending-down-icon" />,
  Trophy: () => <span data-testid="trophy-icon" />,
}));

// --- Test Data ---

function makeTrendCard(overrides: Partial<TrendCard>): TrendCard {
  return {
    card_name: "Test Card",
    early_count: 100,
    late_count: 200,
    early_pct: 5.0,
    late_pct: 10.0,
    delta: 5.0,
    ...overrides,
  };
}

const surgingCards: TrendCard[] = [
  makeTrendCard({
    card_name: "Night Stretcher",
    early_pct: 5.0,
    late_pct: 12.3,
    delta: 7.3,
    archetypes: [
      { archetype: "Dragapult ex", early_pct: 10, late_pct: 20, delta: 10.0 },
    ],
  }),
  makeTrendCard({
    card_name: "Buddy-Buddy Poffin",
    early_pct: 10.0,
    late_pct: 16.7,
    delta: 6.7,
  }),
];

const decliningCards: TrendCard[] = [
  makeTrendCard({
    card_name: "Nest Ball",
    early_pct: 20.0,
    late_pct: 6.7,
    delta: -13.3,
  }),
  makeTrendCard({
    card_name: "Ultra Ball",
    early_pct: 15.0,
    late_pct: 11.2,
    delta: -3.8,
  }),
];

const baseTrends: TrendsData = {
  midpoint: "2026-02-15",
  early_decks: 2000,
  late_decks: 3000,
  surging: surgingCards,
  declining: decliningCards,
};

const baseWinningEdge: WinningEdgeCard[] = [
  { card_name: "Prime Catcher", field_pct: 30.0, win_pct: 55.0, edge: 25.0, winner_decks: 50, field_decks: 500 },
];

const baseDateRange = { start: "2025-10-01", end: "2026-03-23" };

// --- Tests ---

describe("TrendsClient", () => {
  afterEach(cleanup);

  function renderTrends(overrides: Partial<Parameters<typeof TrendsClient>[0]> = {}) {
    return render(
      <TrendsClient
        trends={baseTrends}
        winningEdge={baseWinningEdge}
        format="ninja-spinner"
        dateRange={baseDateRange}
        {...overrides}
      />,
    );
  }

  it("renders the page title", () => {
    renderTrends();
    expect(screen.getByText("Trends")).toBeInTheDocument();
  });

  it("renders surging and declining section headers", () => {
    renderTrends();
    expect(screen.getByText("Surging Cards")).toBeInTheDocument();
    expect(screen.getByText("Declining Cards")).toBeInTheDocument();
  });

  it("displays surging card names", () => {
    renderTrends();
    expect(screen.getByText("Night Stretcher")).toBeInTheDocument();
    expect(screen.getByText("Buddy-Buddy Poffin")).toBeInTheDocument();
  });

  it("displays declining card names", () => {
    renderTrends();
    expect(screen.getByText("Nest Ball")).toBeInTheDocument();
    expect(screen.getByText("Ultra Ball")).toBeInTheDocument();
  });

  it("shows delta percentages for surging cards", () => {
    renderTrends();
    expect(screen.getByText("+7.3%")).toBeInTheDocument();
    expect(screen.getByText("+6.7%")).toBeInTheDocument();
  });

  it("shows delta percentages for declining cards", () => {
    renderTrends();
    expect(screen.getByText("-13.3%")).toBeInTheDocument();
    expect(screen.getByText("-3.8%")).toBeInTheDocument();
  });

  it("shows early and late percentages in surging table", () => {
    renderTrends();
    expect(screen.getByText("5.0%")).toBeInTheDocument();
    expect(screen.getByText("12.3%")).toBeInTheDocument();
  });

  it("renders the midpoint and deck counts in subtitle", () => {
    renderTrends();
    expect(screen.getByText(/2000 decks/)).toBeInTheDocument();
    expect(screen.getByText(/3000 decks/)).toBeInTheDocument();
    expect(screen.getByText(/2026-02-15/)).toBeInTheDocument();
  });

  it("renders a guide link", () => {
    renderTrends();
    const guideLink = screen.getByText(/How this works/);
    expect(guideLink).toBeInTheDocument();
    expect(guideLink.closest("a")).toHaveAttribute("href", "/ninja-spinner/guide#trends");
  });

  it("renders the winning edge section", () => {
    renderTrends();
    expect(screen.getByText(/Winning Edge/)).toBeInTheDocument();
    expect(screen.getByText("Prime Catcher")).toBeInTheDocument();
    expect(screen.getByText("55.0%")).toBeInTheDocument();
    expect(screen.getByText("+25.0%")).toBeInTheDocument();
  });

  it("renders the bar chart", () => {
    renderTrends();
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
    expect(screen.getByTestId("bar-chart")).toBeInTheDocument();
  });

  it("renders archetype breakdown for surging cards that have archetypes", () => {
    renderTrends();
    expect(screen.getByText("Dragapult ex")).toBeInTheDocument();
    expect(screen.getByText("+10.0%")).toBeInTheDocument();
  });

  it("renders empty tables when surging is empty but declining has data", () => {
    const trends: TrendsData = {
      ...baseTrends,
      surging: [],
    };
    renderTrends({ trends });
    expect(screen.getByText("Surging Cards")).toBeInTheDocument();
    expect(screen.queryByText("Night Stretcher")).not.toBeInTheDocument();
    expect(screen.getByText("Nest Ball")).toBeInTheDocument();
  });

  it("renders empty tables when declining is empty but surging has data", () => {
    const trends: TrendsData = {
      ...baseTrends,
      declining: [],
    };
    renderTrends({ trends });
    expect(screen.getByText("Declining Cards")).toBeInTheDocument();
    expect(screen.queryByText("Nest Ball")).not.toBeInTheDocument();
    expect(screen.getByText("Night Stretcher")).toBeInTheDocument();
  });

  it("renders both sections empty when no trends exist", () => {
    const trends: TrendsData = {
      ...baseTrends,
      surging: [],
      declining: [],
    };
    renderTrends({ trends });
    expect(screen.getByText("Surging Cards")).toBeInTheDocument();
    expect(screen.getByText("Declining Cards")).toBeInTheDocument();
    expect(screen.queryByText("Night Stretcher")).not.toBeInTheDocument();
    expect(screen.queryByText("Nest Ball")).not.toBeInTheDocument();
  });

  it("renders the date filter", () => {
    renderTrends();
    expect(screen.getByTestId("date-filter")).toBeInTheDocument();
  });

  it("renders winning edge empty when no cards provided", () => {
    renderTrends({ winningEdge: [] });
    expect(screen.getByText(/Winning Edge/)).toBeInTheDocument();
    expect(screen.queryByText("Prime Catcher")).not.toBeInTheDocument();
  });
});
