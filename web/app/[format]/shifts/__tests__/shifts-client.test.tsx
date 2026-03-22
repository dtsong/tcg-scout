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

  it("renders archetype group headers", () => {
    render(<ShiftsClient format="ninja-spinner" movements={mockMovements} />);
    expect(screen.getByText("Mega Lucario")).toBeInTheDocument();
    expect(screen.getByText("Dragapult Dusknoir")).toBeInTheDocument();
    expect(screen.getByText("Dragapult Meowth")).toBeInTheDocument();
  });

  it("renders page title", () => {
    render(<ShiftsClient format="ninja-spinner" movements={mockMovements} />);
    expect(screen.getByText("Copy-Count Shifts")).toBeInTheDocument();
  });

  it("shows correct total count across archetypes", () => {
    render(<ShiftsClient format="ninja-spinner" movements={mockMovements} />);
    expect(screen.getByText(/3 shifts across 3 archetypes/)).toBeInTheDocument();
  });

  it("shows card names when archetype is expanded", async () => {
    const user = userEvent.setup();
    render(<ShiftsClient format="ninja-spinner" movements={mockMovements} />);
    // Cards should not be visible before expanding
    expect(screen.queryByText("Night Stretcher")).not.toBeInTheDocument();
    // Click to expand Mega Lucario
    await user.click(screen.getByText("Mega Lucario"));
    expect(screen.getByText("Night Stretcher")).toBeInTheDocument();
  });

  it("filters by direction - Drops only hides rise-only archetypes", async () => {
    const user = userEvent.setup();
    render(<ShiftsClient format="ninja-spinner" movements={mockMovements} />);
    await user.click(screen.getByRole("button", { name: "Drops" }));
    // Dragapult Dusknoir only has an adopted movement, should be hidden
    expect(screen.queryByText("Dragapult Dusknoir")).not.toBeInTheDocument();
    expect(screen.getByText("Mega Lucario")).toBeInTheDocument();
    expect(screen.getByText(/2 shifts across 2 archetypes/)).toBeInTheDocument();
  });

  it("filters by direction - Rises only", async () => {
    const user = userEvent.setup();
    render(<ShiftsClient format="ninja-spinner" movements={mockMovements} />);
    await user.click(screen.getByRole("button", { name: "Rises" }));
    expect(screen.getByText("Dragapult Dusknoir")).toBeInTheDocument();
    expect(screen.queryByText("Mega Lucario")).not.toBeInTheDocument();
    expect(screen.getByText(/1 shift across 1 archetype/)).toBeInTheDocument();
  });

  it("expand all shows all card names", async () => {
    const user = userEvent.setup();
    render(<ShiftsClient format="ninja-spinner" movements={mockMovements} />);
    await user.click(screen.getByText("Expand all"));
    expect(screen.getByText("Night Stretcher")).toBeInTheDocument();
    expect(screen.getByText("Briar")).toBeInTheDocument();
    expect(screen.getByText("Meowth ex")).toBeInTheDocument();
  });

  it("renders empty state when no movements", () => {
    render(<ShiftsClient format="ninja-spinner" movements={[]} />);
    expect(screen.getByText("No significant copy-count shifts detected yet.")).toBeInTheDocument();
  });

  it("renders deck count in archetype header", () => {
    render(<ShiftsClient format="ninja-spinner" movements={mockMovements} />);
    expect(screen.getByText("42 decks")).toBeInTheDocument();
  });

  it("groups are sorted by max delta magnitude", () => {
    render(<ShiftsClient format="ninja-spinner" movements={mockMovements} />);
    const body = document.body.textContent || "";
    const megaIdx = body.indexOf("Mega Lucario");
    const dragIdx = body.indexOf("Dragapult Meowth");
    // Mega Lucario (delta 96) should come before Dragapult Meowth (delta 32)
    expect(megaIdx).toBeGreaterThan(-1);
    expect(dragIdx).toBeGreaterThan(-1);
    expect(megaIdx).toBeLessThan(dragIdx);
  });
});
