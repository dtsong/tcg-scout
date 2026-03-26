import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { ArchetypeMatchups } from "../archetype-matchups";
import type { ArchetypeMatchups as ArchetypeMatchupsType } from "@/app/lib/types";

const mockMatchups: ArchetypeMatchupsType = {
  favorable: [
    { archetype: "Gardevoir ex", win_rate: 0.65, sample_size: 42, ci_lower: 0.55, ci_upper: 0.75 },
    { archetype: "Lugia VSTAR", win_rate: 0.58, sample_size: 31, ci_lower: 0.48, ci_upper: 0.68 },
  ],
  unfavorable: [
    { archetype: "Charizard ex", win_rate: 0.38, sample_size: 55, ci_lower: 0.28, ci_upper: 0.48 },
    { archetype: "Raging Bolt ex", win_rate: 0.42, sample_size: 36, ci_lower: 0.32, ci_upper: 0.52 },
  ],
};

describe("ArchetypeMatchups", () => {
  afterEach(cleanup);

  it("renders favorable and unfavorable sections", () => {
    render(<ArchetypeMatchups matchups={mockMatchups} source="labs-h2h" format="ninja-spinner" />);
    expect(screen.getByText("Favorable")).toBeInTheDocument();
    expect(screen.getByText("Unfavorable")).toBeInTheDocument();
  });

  it("displays archetype names", () => {
    render(<ArchetypeMatchups matchups={mockMatchups} source="labs-h2h" format="ninja-spinner" />);
    expect(screen.getByText("Gardevoir ex")).toBeInTheDocument();
    expect(screen.getByText("Charizard ex")).toBeInTheDocument();
  });

  it("displays win rate percentages", () => {
    render(<ArchetypeMatchups matchups={mockMatchups} source="labs-h2h" format="ninja-spinner" />);
    expect(screen.getByText("65%")).toBeInTheDocument();
    expect(screen.getByText("38%")).toBeInTheDocument();
  });

  it("renders nothing when both lists are empty", () => {
    const { container } = render(
      <ArchetypeMatchups matchups={{ favorable: [], unfavorable: [] }} source="labs-h2h" format="ninja-spinner" />
    );
    expect(container.firstChild).toBeNull();
  });
});
