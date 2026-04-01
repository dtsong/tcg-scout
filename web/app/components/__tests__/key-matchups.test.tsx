import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";
import { KeyMatchups } from "../key-matchups";
import type { MatchupMatrixData } from "@/app/lib/types";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

afterEach(() => {
  cleanup();
});

const mockCooccurrence: MatchupMatrixData = {
  archetypes: ["Charizard-Pidgeot", "Dragapult-Dusknoir", "Lugia-Archeops"],
  matrix: [
    [0, 2.5, -1.8],
    [-2.5, 0, 1.2],
    [1.8, -1.2, 0],
  ],
  sample_sizes: [
    [0, 15, 12],
    [15, 0, 18],
    [12, 18, 0],
  ],
  source: "co-occurrence",
};

const mockWinRate: MatchupMatrixData = {
  archetypes: ["Charizard-Pidgeot", "Dragapult-Dusknoir", "Lugia-Archeops"],
  matrix: [
    [0.5, 0.62, 0.38],
    [0.38, 0.5, 0.55],
    [0.62, 0.45, 0.5],
  ],
  sample_sizes: [
    [0, 35, 28],
    [35, 0, 40],
    [28, 40, 0],
  ],
  source: "labs-records",
};

describe("KeyMatchups", () => {
  it("renders favorable and unfavorable sections for co-occurrence data", () => {
    render(
      <KeyMatchups
        data={mockCooccurrence}
        archetype="Charizard-Pidgeot"
        format="ninja-spinner"
      />,
    );
    expect(screen.getByText("Favorable")).toBeInTheDocument();
    expect(screen.getByText("Unfavorable")).toBeInTheDocument();
    expect(screen.getByText("Dragapult-Dusknoir")).toBeInTheDocument();
    expect(screen.getByText("Lugia-Archeops")).toBeInTheDocument();
  });

  it("renders win rate percentages for labs data", () => {
    render(
      <KeyMatchups
        data={mockWinRate}
        archetype="Charizard-Pidgeot"
        format="ninja-spinner"
      />,
    );
    expect(screen.getByText("62%")).toBeInTheDocument();
    expect(screen.getByText("38%")).toBeInTheDocument();
  });

  it("renders nothing when archetype not in matrix", () => {
    const { container } = render(
      <KeyMatchups
        data={mockCooccurrence}
        archetype="Unknown-Archetype"
        format="ninja-spinner"
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("includes link to full matchup page", () => {
    render(
      <KeyMatchups
        data={mockCooccurrence}
        archetype="Charizard-Pidgeot"
        format="ninja-spinner"
      />,
    );
    const links = screen.getAllByRole("link", { name: /View full matchup data/ });
    expect(links.length).toBeGreaterThan(0);
    expect(links[0]).toHaveAttribute("href", "/ninja-spinner/matchups");
  });

  it("shows limited data label for low sample sizes", () => {
    const lowSampleData: MatchupMatrixData = {
      archetypes: ["A", "B"],
      matrix: [
        [0.5, 0.65],
        [0.35, 0.5],
      ],
      sample_sizes: [
        [0, 8],
        [8, 0],
      ],
      source: "labs-records",
    };
    render(
      <KeyMatchups data={lowSampleData} archetype="A" format="test" />,
    );
    expect(screen.getAllByText(/Limited data/).length).toBeGreaterThan(0);
  });

  it("shows sample sizes", () => {
    render(
      <KeyMatchups
        data={mockCooccurrence}
        archetype="Charizard-Pidgeot"
        format="ninja-spinner"
      />,
    );
    expect(screen.getAllByText(/n=\d+/).length).toBeGreaterThan(0);
  });
});
