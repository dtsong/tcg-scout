import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { WorkflowDiagram } from "@/app/components/workflow-diagram";

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

describe("WorkflowDiagram", () => {
  afterEach(cleanup);

  it("renders all 6 step titles", () => {
    render(<WorkflowDiagram format="ninja-spinner" />);
    // Each title appears twice (desktop + mobile)
    expect(screen.getAllByText("Check the tier list").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Pick an archetype").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Study the Optimal 60").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Find winning cards").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Track what's changing").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Scout your matchups").length).toBeGreaterThanOrEqual(1);
  });

  it("renders sequential step numbers", () => {
    render(<WorkflowDiagram format="ninja-spinner" />);
    for (let i = 1; i <= 6; i++) {
      expect(screen.getAllByText(String(i)).length).toBeGreaterThanOrEqual(1);
    }
  });

  it("renders step descriptions", () => {
    render(<WorkflowDiagram format="ninja-spinner" />);
    expect(
      screen.getAllByText("See which decks dominate the meta").length
    ).toBeGreaterThanOrEqual(1);
    expect(
      screen.getAllByText("Get the consensus decklist").length
    ).toBeGreaterThanOrEqual(1);
  });

  it("links use the provided format prop", () => {
    render(<WorkflowDiagram format="nihil-zero" />);
    const links = screen.getAllByRole("link");
    const hrefs = links.map((l) => l.getAttribute("href"));
    expect(hrefs).toContain("/nihil-zero");
    expect(hrefs).toContain("/nihil-zero/archetypes");
    expect(hrefs).toContain("/nihil-zero/optimal-60");
    expect(hrefs).toContain("/nihil-zero/card-analysis");
    expect(hrefs).toContain("/nihil-zero/trends");
  });

  it("compact mode renders without link elements", () => {
    render(<WorkflowDiagram format="ninja-spinner" compact />);
    const links = screen.queryAllByRole("link");
    expect(links).toHaveLength(0);
  });
});
