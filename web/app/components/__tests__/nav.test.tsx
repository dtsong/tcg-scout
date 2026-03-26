import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Nav } from "@/app/components/nav";

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/ninja-spinner",
  useRouter: () => ({ push: vi.fn() }),
}));

const FORMATS = [
  { slug: "ninja-spinner", name: "Ninja Spinner", name_en: "Ninja Spinner", status: "active" as const, tournament_count: 100, deck_count: 1000, description: "Current rotation format", dataset_start: "2025-01-01", dataset_end: "2026-03-26" },
  { slug: "nihil-zero", name: "Nihil Zero", name_en: "Nihil Zero", status: "frozen" as const, tournament_count: 430, deck_count: 5000, description: "Previous rotation format", dataset_start: "2024-01-01", dataset_end: "2024-12-31" },
];

describe("Nav", () => {
  afterEach(cleanup);

  it("renders a mobile menu button visible only on small screens", () => {
    render(<Nav format="ninja-spinner" formats={FORMATS} />);
    const btn = screen.getByTestId("mobile-menu-button");
    expect(btn).toBeInTheDocument();
  });

  it("opens the mobile drawer when menu button is clicked", async () => {
    const user = userEvent.setup();
    render(<Nav format="ninja-spinner" formats={FORMATS} />);
    const btn = screen.getByTestId("mobile-menu-button");
    await user.click(btn);
    expect(screen.getByTestId("mobile-drawer")).toBeInTheDocument();
  });

  it("shows all nav links in mobile drawer", async () => {
    const user = userEvent.setup();
    render(<Nav format="ninja-spinner" formats={FORMATS} />);
    await user.click(screen.getByTestId("mobile-menu-button"));
    const drawer = screen.getByTestId("mobile-drawer");
    expect(drawer).toHaveTextContent("Dashboard");
    expect(drawer).toHaveTextContent("Matchups");
    expect(drawer).toHaveTextContent("Archetypes");
    expect(drawer).toHaveTextContent("Guide");
  });

  it("closes drawer when a link is clicked", async () => {
    const user = userEvent.setup();
    render(<Nav format="ninja-spinner" formats={FORMATS} />);
    await user.click(screen.getByTestId("mobile-menu-button"));
    const dashLink = screen.getByTestId("mobile-drawer").querySelector('a[href="/ninja-spinner"]');
    await user.click(dashLink!);
    expect(screen.queryByTestId("mobile-drawer")).not.toBeInTheDocument();
  });

  it("closes drawer when close button is clicked", async () => {
    const user = userEvent.setup();
    render(<Nav format="ninja-spinner" formats={FORMATS} />);
    await user.click(screen.getByTestId("mobile-menu-button"));
    await user.click(screen.getByTestId("mobile-drawer-close"));
    expect(screen.queryByTestId("mobile-drawer")).not.toBeInTheDocument();
  });
});
