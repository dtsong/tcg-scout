import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BuylistClient } from "../buylist-client";
import type { BuylistCard, StapleCard } from "@/app/lib/types";

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

vi.mock("next/navigation", () => ({
  useParams: () => ({ format: "ninja-spinner" }),
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

vi.mock("lucide-react", () => ({
  ExternalLink: () => <span data-testid="external-link-icon" />,
  ArrowUpDown: () => <span data-testid="arrow-updown-icon" />,
  Search: () => <span data-testid="search-icon" />,
}));

// --- Test Data ---

function makeBuylistCard(overrides: Partial<BuylistCard>): BuylistCard {
  return {
    card_name: "Test Card",
    card_id: null,
    set_code: null,
    set_number: null,
    priority_score: 10.0,
    core_flex: "core",
    archetypes: ["Charizard ex"],
    avg_copies: 2.5,
    inclusion_rate: 0.85,
    ...overrides,
  };
}

function makeStapleCard(overrides: Partial<StapleCard>): StapleCard {
  return {
    card_name: "Staple Card",
    deck_count: 100,
    usage_pct: 75.0,
    avg_copies: 3.0,
    ...overrides,
  };
}

const mockBuylist: BuylistCard[] = [
  makeBuylistCard({
    card_name: "Charizard ex",
    priority_score: 25.3,
    core_flex: "core",
    archetypes: ["Charizard ex", "Charizard Pidgeot"],
    avg_copies: 3.0,
    inclusion_rate: 0.95,
  }),
  makeBuylistCard({
    card_name: "Rare Candy",
    priority_score: 18.7,
    core_flex: "core",
    archetypes: ["Charizard ex", "Gardevoir ex", "Mewtwo ex"],
    avg_copies: 4.0,
    inclusion_rate: 0.88,
  }),
  makeBuylistCard({
    card_name: "Iono",
    priority_score: 12.1,
    core_flex: "flex",
    archetypes: ["Dragapult ex"],
    avg_copies: 2.0,
    inclusion_rate: 0.60,
  }),
];

const mockStaples: StapleCard[] = [
  makeStapleCard({ card_name: "Boss's Orders", usage_pct: 92.0, avg_copies: 2.0, deck_count: 450 }),
  makeStapleCard({ card_name: "Professor's Research", usage_pct: 88.5, avg_copies: 3.0, deck_count: 420 }),
];

const mockFlex: StapleCard[] = [
  makeStapleCard({ card_name: "Switch", usage_pct: 45.0, avg_copies: 1.5, deck_count: 200 }),
];

const baseDateRange = { start: "2025-10-01", end: "2026-03-23" };

// --- Tests ---

describe("BuylistClient", () => {
  afterEach(cleanup);

  function renderBuylist(overrides: Partial<Parameters<typeof BuylistClient>[0]> = {}) {
    return render(
      <BuylistClient
        buylist={mockBuylist}
        staples={mockStaples}
        flex={mockFlex}
        dateRange={baseDateRange}
        {...overrides}
      />,
    );
  }

  it("renders the page title", () => {
    renderBuylist();
    expect(screen.getByText("Buy List")).toBeInTheDocument();
  });

  it("renders card names from buylist data", () => {
    renderBuylist();
    expect(screen.getByText("Charizard ex")).toBeInTheDocument();
    expect(screen.getByText("Rare Candy")).toBeInTheDocument();
    expect(screen.getByText("Iono")).toBeInTheDocument();
  });

  it("displays priority scores", () => {
    renderBuylist();
    expect(screen.getByText("25.3")).toBeInTheDocument();
    expect(screen.getByText("18.7")).toBeInTheDocument();
    expect(screen.getByText("12.1")).toBeInTheDocument();
  });

  it("displays avg copies", () => {
    renderBuylist();
    expect(screen.getByText("3.0")).toBeInTheDocument();
    expect(screen.getByText("4.0")).toBeInTheDocument();
    expect(screen.getByText("2.0")).toBeInTheDocument();
  });

  it("displays inclusion rates as percentages", () => {
    renderBuylist();
    expect(screen.getByText("95.0%")).toBeInTheDocument();
    expect(screen.getByText("88.0%")).toBeInTheDocument();
    expect(screen.getByText("60.0%")).toBeInTheDocument();
  });

  it("displays archetype names for each card", () => {
    renderBuylist();
    // Charizard ex card shows first 2 archetypes
    expect(screen.getByText(/Charizard Pidgeot/)).toBeInTheDocument();
    // Rare Candy has 3 archetypes, shows first 2 + "+1"
    expect(screen.getByText(/Gardevoir ex/)).toBeInTheDocument();
    expect(screen.getByText(/\+1/)).toBeInTheDocument();
  });

  it("shows card count in subtitle", () => {
    renderBuylist();
    expect(screen.getByText(/3 cards across S\/A\/B tier archetypes/)).toBeInTheDocument();
  });

  it("renders the date filter", () => {
    renderBuylist();
    expect(screen.getByTestId("date-filter")).toBeInTheDocument();
  });

  it("renders a guide link", () => {
    renderBuylist();
    const guideLink = screen.getByText(/How this works/);
    expect(guideLink).toBeInTheDocument();
    expect(guideLink.closest("a")).toHaveAttribute("href", "/ninja-spinner/guide#buy-list");
  });

  it("shows tab counts for Full List, Staples, and Flex", () => {
    renderBuylist();
    const fullListTab = screen.getByRole("button", { name: /Full List/i });
    const staplesTab = screen.getByRole("button", { name: /Staples/i });
    const flexTab = screen.getByRole("button", { name: /Flex/i });

    expect(fullListTab).toHaveTextContent("3");
    expect(staplesTab).toHaveTextContent("2");
    expect(flexTab).toHaveTextContent("1");
  });

  it("switches to Staples tab and shows staple cards", async () => {
    const user = userEvent.setup();
    renderBuylist();

    await user.click(screen.getByRole("button", { name: /Staples/i }));

    expect(screen.getByText("Boss's Orders")).toBeInTheDocument();
    expect(screen.getByText("Professor's Research")).toBeInTheDocument();
    // Full List cards should not be visible
    expect(screen.queryByText("Rare Candy")).not.toBeInTheDocument();
  });

  it("switches to Flex tab and shows flex cards", async () => {
    const user = userEvent.setup();
    renderBuylist();

    await user.click(screen.getByRole("button", { name: /Flex/i }));

    expect(screen.getByText("Switch")).toBeInTheDocument();
    // Full List cards should not be visible
    expect(screen.queryByText("Rare Candy")).not.toBeInTheDocument();
  });

  it("shows staple usage percentages on Staples tab", async () => {
    const user = userEvent.setup();
    renderBuylist();

    await user.click(screen.getByRole("button", { name: /Staples/i }));

    expect(screen.getByText("92.0%")).toBeInTheDocument();
    expect(screen.getByText("88.5%")).toBeInTheDocument();
  });

  it("shows deck counts on Staples tab", async () => {
    const user = userEvent.setup();
    renderBuylist();

    await user.click(screen.getByRole("button", { name: /Staples/i }));

    expect(screen.getByText("450")).toBeInTheDocument();
    expect(screen.getByText("420")).toBeInTheDocument();
  });

  it("renders empty state when buylist is empty", () => {
    renderBuylist({ buylist: [], staples: [], flex: [] });
    expect(screen.getByText(/0 cards across S\/A\/B tier archetypes/)).toBeInTheDocument();
    expect(screen.getByText("No results found")).toBeInTheDocument();
  });

  it("renders TCGPlayer links for each card", () => {
    renderBuylist();
    const links = screen.getAllByTestId("external-link-icon");
    expect(links).toHaveLength(3);
  });

  it("sorts by priority score when column header is clicked", async () => {
    const user = userEvent.setup();
    renderBuylist();

    // Click Priority header to sort (default desc)
    const priorityHeader = screen.getByText("Priority");
    await user.click(priorityHeader);

    const rows = screen.getAllByRole("row");
    // Row 0 is header, data rows start at index 1
    const firstDataRow = rows[1];
    const lastDataRow = rows[rows.length - 1];

    // Descending: highest priority first
    expect(firstDataRow).toHaveTextContent("25.3");
    expect(lastDataRow).toHaveTextContent("12.1");
  });

  it("sorts ascending on second click of priority header", async () => {
    const user = userEvent.setup();
    renderBuylist();

    const priorityHeader = screen.getByText("Priority");
    // First click: desc
    await user.click(priorityHeader);
    // Second click: asc
    await user.click(priorityHeader);

    const rows = screen.getAllByRole("row");
    const firstDataRow = rows[1];
    const lastDataRow = rows[rows.length - 1];

    // Ascending: lowest priority first
    expect(firstDataRow).toHaveTextContent("12.1");
    expect(lastDataRow).toHaveTextContent("25.3");
  });

  it("filters cards by search input", async () => {
    const user = userEvent.setup();
    renderBuylist();

    const searchInput = screen.getByPlaceholderText("Search cards...");
    await user.type(searchInput, "Rare");

    expect(screen.getByText("Rare Candy")).toBeInTheDocument();
    expect(screen.queryByText("Charizard ex")).not.toBeInTheDocument();
    expect(screen.queryByText("Iono")).not.toBeInTheDocument();
  });
});
