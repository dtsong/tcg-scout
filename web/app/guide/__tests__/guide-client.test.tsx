import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { GuideClient } from "../guide-client";

describe("GuideClient", () => {
  afterEach(cleanup);

  it("renders the page heading", () => {
    render(<GuideClient />);
    expect(screen.getByText("How Scout Works")).toBeInTheDocument();
  });

  it("renders all scenario cards", () => {
    render(<GuideClient />);
    expect(
      screen.getByText("Pick a deck for this weekend")
    ).toBeInTheDocument();
    expect(screen.getByText("Find cards that actually win")).toBeInTheDocument();
    expect(screen.getByText("Track what's changing")).toBeInTheDocument();
    expect(screen.getByText("Scout a matchup")).toBeInTheDocument();
    expect(screen.getByText("Study winning decklists")).toBeInTheDocument();
  });

  it("renders all tool section headings", () => {
    render(<GuideClient />);
    // Use getAllByText since some names also appear in the glossary "Found on" column
    expect(screen.getAllByText("Dashboard").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Archetypes").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Format Edge").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Cards").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Buy List").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Trends").length).toBeGreaterThanOrEqual(1);
    expect(
      screen.getAllByText("Champions League").length
    ).toBeGreaterThanOrEqual(1);
  });

  it("has first section (Dashboard) open by default", () => {
    render(<GuideClient />);
    expect(screen.getByText(/Tiers are based on meta share/)).toBeInTheDocument();
  });

  it("expands a collapsed section on click", async () => {
    const user = userEvent.setup();
    render(<GuideClient />);
    // Format Edge accordion content should be collapsed initially
    // Check for text that only appears in the accordion body (not the glossary)
    expect(
      screen.queryByText(/overrepresented in top-4 finishing decks/)
    ).not.toBeInTheDocument();
    // Click to expand - target the button specifically
    const formatEdgeButton = screen
      .getAllByText("Format Edge")
      .find((el) => el.tagName === "SPAN");
    await user.click(formatEdgeButton!);
    expect(
      screen.getByText(/overrepresented in top-4 finishing decks/)
    ).toBeInTheDocument();
  });

  it("renders the glossary table", () => {
    render(<GuideClient />);
    expect(screen.getByText("Metric Glossary")).toBeInTheDocument();
    expect(screen.getByText("Meta share")).toBeInTheDocument();
    expect(screen.getByText("Weighted share")).toBeInTheDocument();
    expect(screen.getByText("Winning edge")).toBeInTheDocument();
    expect(screen.getByText("Top-4 edge")).toBeInTheDocument();
  });
});
