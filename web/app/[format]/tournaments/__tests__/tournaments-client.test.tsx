import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { TournamentsClient } from "../tournaments-client";
import type {
  CityLeagueIndex,
  CityLeagueTournament,
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

vi.mock("@/app/components/sprite-row", () => ({
  SpriteRow: ({ filenames }: { filenames: string[] }) => (
    <span data-testid="sprite-row">{filenames.join(",")}</span>
  ),
}));

vi.mock("@/app/components/tier-badge", () => ({
  TierBadge: ({ tier }: { tier: string }) => (
    <span data-testid="tier-badge">{tier}</span>
  ),
}));

// --- Helpers ---

function makeTournament(
  overrides: Partial<CityLeagueTournament> = {},
): CityLeagueTournament {
  return {
    id: "t-1",
    name: "Tokyo City League",
    date: "2026-03-20",
    prefecture: "Tokyo",
    player_count: 64,
    source_url: "https://example.com/tournament/1",
    top_finishers: [
      {
        standing: 1,
        player_name: "Ash K.",
        archetype: "Charizard Pidgeot",
        slug: "charizard-pidgeot",
        sprite_filenames: ["charizard.png", "pidgeot.png"],
        tier: "S",
      },
      {
        standing: 2,
        player_name: "Misty W.",
        archetype: "Dragapult Dusknoir",
        slug: "dragapult-dusknoir",
        sprite_filenames: ["dragapult.png"],
        tier: "A",
      },
    ],
    archetype_distribution: [
      {
        archetype: "Charizard Pidgeot",
        slug: "charizard-pidgeot",
        count: 10,
        share: 0.156,
        sprite_filenames: ["charizard.png"],
      },
    ],
    ...overrides,
  };
}

function makeIndex(
  tournaments: CityLeagueTournament[] = [makeTournament()],
  overrides: Partial<CityLeagueIndex> = {},
): CityLeagueIndex {
  return {
    generated_at: "2026-03-21T00:00:00Z",
    tournament_count: tournaments.length,
    deck_count: tournaments.reduce(
      (sum, t) => sum + (t.player_count ?? 0),
      0,
    ),
    date_range: { start: "2026-03-01", end: "2026-03-21" },
    rising_archetypes: [],
    recent_winners: [
      {
        archetype: "Charizard Pidgeot",
        slug: "charizard-pidgeot",
        sprite_filenames: ["charizard.png"],
        date: "2026-03-20",
        tournament_name: "Tokyo City League",
        player_name: "Ash K.",
      },
    ],
    tournaments,
    ...overrides,
  };
}

const defaultDateRange = { start: "2026-03-01", end: "2026-03-21" };

// --- Tests ---

describe("TournamentsClient", () => {
  afterEach(cleanup);

  it("renders tournament names", () => {
    render(
      <TournamentsClient
        format="ninja-spinner"
        index={makeIndex()}
        dateRange={defaultDateRange}
      />,
    );
    expect(screen.getByText("Tokyo City League")).toBeInTheDocument();
  });

  it("shows formatted dates in group headers", () => {
    render(
      <TournamentsClient
        format="ninja-spinner"
        index={makeIndex()}
        dateRange={defaultDateRange}
      />,
    );
    expect(screen.getByText("Mar 20, 2026")).toBeInTheDocument();
  });

  it("shows deck count in the header stats", () => {
    render(
      <TournamentsClient
        format="ninja-spinner"
        index={makeIndex()}
        dateRange={defaultDateRange}
      />,
    );
    // The deck count appears next to the "Decks" label
    const decksLabel = screen.getByText("Decks");
    const decksValue = decksLabel.parentElement?.querySelector(
      ".font-mono",
    );
    expect(decksValue?.textContent).toBe("64");
  });

  it("shows tournament count in the header", () => {
    const index = makeIndex([
      makeTournament(),
      makeTournament({ id: "t-2", name: "Osaka CL" }),
    ]);
    render(
      <TournamentsClient
        format="ninja-spinner"
        index={index}
        dateRange={defaultDateRange}
      />,
    );
    // The tournament count appears next to the "Tournaments" label
    const tournamentsLabel = screen.getByText("Tournaments", {
      selector: "span",
    });
    const tournamentsValue = tournamentsLabel.parentElement?.querySelector(
      ".font-mono",
    );
    expect(tournamentsValue?.textContent).toBe("2");
  });

  it("renders table column headers", () => {
    render(
      <TournamentsClient
        format="ninja-spinner"
        index={makeIndex()}
        dateRange={defaultDateRange}
      />,
    );
    expect(screen.getByText("Date")).toBeInTheDocument();
    expect(screen.getByText("Tournament")).toBeInTheDocument();
    expect(screen.getByText("Prefecture")).toBeInTheDocument();
    expect(screen.getByText("Players")).toBeInTheDocument();
    expect(screen.getByText("Winner")).toBeInTheDocument();
  });

  it("renders empty state when no tournaments", () => {
    const emptyIndex = makeIndex([], {
      tournament_count: 0,
      deck_count: 0,
      recent_winners: [],
    });
    render(
      <TournamentsClient
        format="ninja-spinner"
        index={emptyIndex}
        dateRange={defaultDateRange}
      />,
    );
    expect(
      screen.getByText("No tournaments found for this time window."),
    ).toBeInTheDocument();
  });

  it("renders multiple tournaments grouped by date", () => {
    const tournaments = [
      makeTournament({ id: "t-1", name: "Tokyo CL", date: "2026-03-20" }),
      makeTournament({ id: "t-2", name: "Osaka CL", date: "2026-03-20" }),
      makeTournament({ id: "t-3", name: "Nagoya CL", date: "2026-03-19" }),
    ];
    render(
      <TournamentsClient
        format="ninja-spinner"
        index={makeIndex(tournaments)}
        dateRange={defaultDateRange}
      />,
    );
    // Latest date group (Mar 20) is expanded by default
    expect(screen.getByText("Tokyo CL")).toBeInTheDocument();
    expect(screen.getByText("Osaka CL")).toBeInTheDocument();
    // Older date group (Mar 19) is collapsed by default
    expect(screen.queryByText("Nagoya CL")).not.toBeInTheDocument();
    // Both date group headers should appear
    expect(screen.getByText("Mar 20, 2026")).toBeInTheDocument();
    expect(screen.getByText("Mar 19, 2026")).toBeInTheDocument();
    // Click the collapsed group header to expand it
    fireEvent.click(screen.getByText("Mar 19, 2026"));
    expect(screen.getByText("Nagoya CL")).toBeInTheDocument();
  });

  it("collapses an expanded date group on click", () => {
    const tournaments = [
      makeTournament({ id: "t-1", name: "Tokyo CL", date: "2026-03-20" }),
      makeTournament({ id: "t-2", name: "Osaka CL", date: "2026-03-20" }),
    ];
    render(
      <TournamentsClient
        format="ninja-spinner"
        index={makeIndex(tournaments)}
        dateRange={defaultDateRange}
      />,
    );
    // Latest group is expanded by default
    expect(screen.getByText("Tokyo CL")).toBeInTheDocument();
    // Click to collapse
    fireEvent.click(screen.getByText("Mar 20, 2026"));
    expect(screen.queryByText("Tokyo CL")).not.toBeInTheDocument();
  });

  it("shows group tournament count label", () => {
    const tournaments = [
      makeTournament({ id: "t-1", name: "Tokyo CL", date: "2026-03-20" }),
      makeTournament({ id: "t-2", name: "Osaka CL", date: "2026-03-20" }),
    ];
    render(
      <TournamentsClient
        format="ninja-spinner"
        index={makeIndex(tournaments)}
        dateRange={defaultDateRange}
      />,
    );
    expect(screen.getByText("2 tournaments")).toBeInTheDocument();
  });

  it("shows singular tournament label for single-tournament group", () => {
    render(
      <TournamentsClient
        format="ninja-spinner"
        index={makeIndex()}
        dateRange={defaultDateRange}
      />,
    );
    expect(screen.getByText("1 tournament")).toBeInTheDocument();
  });

  it("renders winner sprite row for tournaments", () => {
    render(
      <TournamentsClient
        format="ninja-spinner"
        index={makeIndex()}
        dateRange={defaultDateRange}
      />,
    );
    const spriteRows = screen.getAllByTestId("sprite-row");
    expect(spriteRows.length).toBeGreaterThan(0);
  });

  it("displays player count placeholder when missing", () => {
    const tournament = makeTournament({ player_count: null });
    render(
      <TournamentsClient
        format="ninja-spinner"
        index={makeIndex([tournament])}
        dateRange={defaultDateRange}
      />,
    );
    expect(screen.getByText("--")).toBeInTheDocument();
  });

  it("renders the page title and description", () => {
    render(
      <TournamentsClient
        format="ninja-spinner"
        index={makeIndex()}
        dateRange={defaultDateRange}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "Tournaments" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("City League results across Japan, sorted by date."),
    ).toBeInTheDocument();
  });

  it("renders latest winner link in header", () => {
    render(
      <TournamentsClient
        format="ninja-spinner"
        index={makeIndex()}
        dateRange={defaultDateRange}
      />,
    );
    const winnerLink = screen.getByRole("link", {
      name: /Charizard Pidgeot/,
    });
    expect(winnerLink).toHaveAttribute(
      "href",
      "/ninja-spinner/archetypes/charizard-pidgeot",
    );
  });

  it("renders rising archetypes when present", () => {
    const index = makeIndex([], {
      tournament_count: 0,
      deck_count: 0,
      recent_winners: [],
      rising_archetypes: [
        {
          archetype: "Lugia Archeops",
          slug: "lugia-archeops",
          trend: "up",
          trend_delta: 3.5,
          sprite_filenames: ["lugia.png"],
          tier: "A",
        },
      ],
    });
    render(
      <TournamentsClient
        format="ninja-spinner"
        index={index}
        dateRange={defaultDateRange}
      />,
    );
    expect(screen.getByText("Lugia Archeops")).toBeInTheDocument();
    expect(screen.getByText("+3.5")).toBeInTheDocument();
  });

  it("renders the date filter component", () => {
    render(
      <TournamentsClient
        format="ninja-spinner"
        index={makeIndex()}
        dateRange={defaultDateRange}
      />,
    );
    expect(screen.getByTestId("date-filter")).toBeInTheDocument();
  });
});
