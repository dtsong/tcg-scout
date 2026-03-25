import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import type { ArchetypeReport, ConsensusCard, PlacementBracket, NotableTech } from "@/app/lib/types";

// Mock next/link
import { vi } from "vitest";
vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

// Mock recharts to avoid canvas issues in test
vi.mock("recharts", () => ({
  LineChart: ({ children }: { children: React.ReactNode }) => <div data-testid="line-chart">{children}</div>,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Legend: () => null,
}));

import { ConsensusDeck } from "../consensus-deck";
import { PlacementDistribution } from "../placement-distribution";
import { NotableTechs } from "../notable-techs";

const mockCards: ConsensusCard[] = [
  {
    card_name: "Ultra Ball",
    count: 4,
    category: "Trainer",
    weighted_inclusion_pct: 98.5,
    weighted_avg_copies: 4.0,
    confidence: 0.96,
    consensus: "core",
  },
  {
    card_name: "Charizard ex",
    count: 3,
    category: "Pokemon",
    weighted_inclusion_pct: 95.0,
    weighted_avg_copies: 3.0,
    confidence: 0.94,
    consensus: "core",
  },
  {
    card_name: "Fire Energy",
    count: 10,
    category: "Energy",
    weighted_inclusion_pct: 90.0,
    weighted_avg_copies: 10.0,
    confidence: 0.9,
    consensus: "core",
  },
  {
    card_name: "Solrock",
    count: 1,
    category: "Pokemon",
    weighted_inclusion_pct: 35.0,
    weighted_avg_copies: 1.0,
    confidence: 0.3,
    consensus: "tech",
  },
];

describe("ConsensusDeck", () => {
  afterEach(cleanup);

  it("renders cards grouped by category", () => {
    render(
      <ConsensusDeck
        cards={mockCards}
        qualityScore={82.3}
        totalPokemon={4}
        totalTrainer={4}
        totalEnergy={10}
        format="nihil-zero"
      />,
    );

    expect(screen.getByRole("link", { name: "Ultra Ball" })).toHaveAttribute("href", "/nihil-zero/cards/ultra-ball");
    expect(screen.getByRole("link", { name: "Charizard ex" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Solrock" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Fire Energy" })).toBeDefined();
  });

  it("shows consensus labels", () => {
    render(
      <ConsensusDeck
        cards={mockCards}
        qualityScore={82.3}
        totalPokemon={4}
        totalTrainer={4}
        totalEnergy={10}
        format="nihil-zero"
      />,
    );

    const corePills = screen.getAllByText("core");
    expect(corePills.length).toBe(3);
    expect(screen.getByText("tech")).toBeDefined();
  });

  it("shows quality score", () => {
    render(
      <ConsensusDeck
        cards={mockCards}
        qualityScore={82.3}
        totalPokemon={4}
        totalTrainer={4}
        totalEnergy={10}
        format="nihil-zero"
      />,
    );

    expect(screen.getByText("82.3")).toBeDefined();
  });
});

describe("PlacementDistribution", () => {
  afterEach(cleanup);

  const brackets: PlacementBracket[] = [
    { bracket: "1st", count: 4, pct: 8.5 },
    { bracket: "2nd", count: 3, pct: 6.4 },
    { bracket: "5th-8th", count: 10, pct: 21.3 },
  ];

  it("renders all brackets", () => {
    render(<PlacementDistribution brackets={brackets} />);

    expect(screen.getByText("1st")).toBeDefined();
    expect(screen.getByText("2nd")).toBeDefined();
    expect(screen.getByText("5th-8th")).toBeDefined();
  });

  it("shows count for each bracket", () => {
    render(<PlacementDistribution brackets={brackets} />);

    expect(screen.getByText("4")).toBeDefined();
    expect(screen.getByText("3")).toBeDefined();
    expect(screen.getByText("10")).toBeDefined();
  });

  it("returns null for empty brackets", () => {
    const { container } = render(<PlacementDistribution brackets={[]} />);
    expect(container.innerHTML).toBe("");
  });
});

describe("NotableTechs", () => {
  afterEach(cleanup);

  const techs: NotableTech[] = [
    {
      card_name: "Solrock",
      event: "appeared",
      week: "2026-02-03",
      from_pct: 0,
      to_pct: 85,
    },
    {
      card_name: "Old Card",
      event: "disappeared",
      week: "2026-02-10",
      from_pct: 60,
      to_pct: 5,
    },
  ];

  it("renders tech events", () => {
    render(<NotableTechs techs={techs} format="nihil-zero" />);

    expect(screen.getByText("Solrock")).toBeDefined();
    expect(screen.getByText("Old Card")).toBeDefined();
  });

  it("shows event badges", () => {
    render(<NotableTechs techs={techs} format="nihil-zero" />);

    expect(screen.getByText("New")).toBeDefined();
    expect(screen.getByText("Dropped")).toBeDefined();
  });

  it("returns null for empty techs", () => {
    const { container } = render(<NotableTechs techs={[]} format="nihil-zero" />);
    expect(container.innerHTML).toBe("");
  });
});
