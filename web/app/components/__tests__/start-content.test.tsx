import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { StartContent } from "@/app/components/start-content";

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

vi.mock("next/navigation", () => ({
  useParams: () => ({ format: "ninja-spinner" }),
}));

describe("StartContent", () => {
  afterEach(cleanup);

  it("renders the hero headline", () => {
    render(<StartContent />);
    expect(screen.getByText("Everything in one place")).toBeInTheDocument();
  });

  it("renders the primary CTA linking to the active format", () => {
    render(<StartContent />);
    const cta = screen.getByRole("link", { name: /Jump into the meta/ });
    expect(cta).toHaveAttribute("href", "/ninja-spinner");
  });

  it("renders the Nihil Zero post-rotation callout", () => {
    render(<StartContent />);
    expect(screen.getByText("Post-rotation preview")).toBeInTheDocument();
    expect(
      screen.getByText(/Nihil Zero mirrors the upcoming international/)
    ).toBeInTheDocument();
  });

  it("renders the workflow section heading", () => {
    render(<StartContent />);
    expect(screen.getByText("How to use Scout")).toBeInTheDocument();
  });

  it("renders all 6 feature highlight cards", () => {
    render(<StartContent />);
    expect(screen.getByText("Read the meta")).toBeInTheDocument();
    expect(screen.getByText("Pick a deck")).toBeInTheDocument();
    // "Find winning cards" and "Track what's changing" also appear in the
    // workflow diagram, so use getAllByText
    expect(screen.getAllByText("Find winning cards").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Track what's changing").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Scout matchups")).toBeInTheDocument();
    expect(screen.getByText("Study decklists")).toBeInTheDocument();
  });

  it("feature highlight links point to format-prefixed paths", () => {
    render(<StartContent />);
    const links = screen.getAllByRole("link");
    const hrefs = links.map((l) => l.getAttribute("href"));
    expect(hrefs).toContain("/ninja-spinner/optimal-60");
    expect(hrefs).toContain("/ninja-spinner/card-analysis");
    expect(hrefs).toContain("/ninja-spinner/trends");
    expect(hrefs).toContain("/ninja-spinner/champions");
  });

  it("renders format spotlight with both formats", () => {
    render(<StartContent />);
    expect(screen.getByText("Ninja Spinner")).toBeInTheDocument();
    expect(screen.getByText("Nihil Zero")).toBeInTheDocument();
  });

  it("renders guide cross-reference link", () => {
    render(<StartContent />);
    expect(
      screen.getByText("Looking for metric definitions?")
    ).toBeInTheDocument();
    const guideLink = screen.getByRole("link", { name: /Guide/ });
    expect(guideLink).toHaveAttribute("href", "/ninja-spinner/guide");
  });

  it("renders footer CTA and social links", () => {
    render(<StartContent />);
    expect(screen.getByText("Ready to start?")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Open the dashboard/ })
    ).toHaveAttribute("href", "/ninja-spinner");
    expect(screen.getByRole("link", { name: /GitHub/ })).toHaveAttribute(
      "href",
      "https://github.com/dtsong/tcg-scout"
    );
  });
});
