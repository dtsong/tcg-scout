import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ShiftsClient } from "../shifts-client";
import type { MetaEvolutionMovement } from "@/app/lib/types";

const mockMovements: MetaEvolutionMovement[] = [
  {
    card: "Night Stretcher",
    archetype: "Mega Lucario",
    archetype_slug: "mega-lucario",
    deck_count: 42,
    direction: "dropped",
    from_pct: 96,
    to_pct: 0,
    delta: 96,
    week: "2026-03-16",
  },
  {
    card: "Briar",
    archetype: "Dragapult Dusknoir",
    archetype_slug: "dragapult-dusknoir",
    deck_count: 30,
    direction: "adopted",
    from_pct: 26,
    to_pct: 50,
    delta: 24,
    week: "2026-03-16",
  },
  {
    card: "Meowth ex",
    archetype: "Dragapult Meowth",
    archetype_slug: "dragapult-meowth",
    deck_count: 15,
    direction: "dropped",
    from_pct: 50,
    to_pct: 18,
    delta: 32,
    week: "2026-03-09",
  },
];

describe("ShiftsClient", () => {
  afterEach(cleanup);

  it("renders all movements", () => {
    render(<ShiftsClient format="ninja-spinner" movements={mockMovements} />);
    expect(screen.getByText("Night Stretcher")).toBeInTheDocument();
    expect(screen.getByText("Briar")).toBeInTheDocument();
    expect(screen.getByText("Meowth ex")).toBeInTheDocument();
  });

  it("renders page title", () => {
    render(<ShiftsClient format="ninja-spinner" movements={mockMovements} />);
    expect(screen.getByText("Copy-Count Shifts")).toBeInTheDocument();
  });

  it("shows correct count", () => {
    render(<ShiftsClient format="ninja-spinner" movements={mockMovements} />);
    expect(screen.getByText("3 shifts")).toBeInTheDocument();
  });

  it("filters by direction - Drops only", async () => {
    const user = userEvent.setup();
    render(<ShiftsClient format="ninja-spinner" movements={mockMovements} />);
    await user.click(screen.getByRole("button", { name: "Drops" }));
    expect(screen.getByText("Night Stretcher")).toBeInTheDocument();
    expect(screen.getByText("Meowth ex")).toBeInTheDocument();
    expect(screen.queryByText("Briar")).not.toBeInTheDocument();
    expect(screen.getByText("2 shifts")).toBeInTheDocument();
  });

  it("filters by direction - Rises only", async () => {
    const user = userEvent.setup();
    render(<ShiftsClient format="ninja-spinner" movements={mockMovements} />);
    await user.click(screen.getByRole("button", { name: "Rises" }));
    expect(screen.getByText("Briar")).toBeInTheDocument();
    expect(screen.queryByText("Night Stretcher")).not.toBeInTheDocument();
    expect(screen.getByText("1 shift")).toBeInTheDocument();
  });

  it("renders archetype links", () => {
    render(<ShiftsClient format="ninja-spinner" movements={mockMovements} />);
    const link = screen.getByRole("link", { name: "Mega Lucario" });
    expect(link).toHaveAttribute("href", "/ninja-spinner/archetypes/mega-lucario");
  });

  it("renders empty state when no movements", () => {
    render(<ShiftsClient format="ninja-spinner" movements={[]} />);
    expect(screen.getByText("No significant copy-count shifts detected yet.")).toBeInTheDocument();
  });

  it("renders deck count for movements with data", () => {
    render(<ShiftsClient format="ninja-spinner" movements={mockMovements} />);
    expect(screen.getByText("(42 decks)")).toBeInTheDocument();
  });
});
