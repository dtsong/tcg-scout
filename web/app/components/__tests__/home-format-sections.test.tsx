import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, within } from "@testing-library/react";
import type { FormatInfo } from "@/app/lib/types";
import { HomeFormatSections } from "../home-format-sections";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

afterEach(cleanup);

function fmt(slug: string, status: FormatInfo["status"], extra: Partial<FormatInfo> = {}): FormatInfo {
  return {
    slug,
    name: slug[0].toUpperCase() + slug.slice(1),
    name_en: `${slug} en`,
    description: `${slug} description`,
    dataset_start: "2026-06-05",
    dataset_end: "2026-08-13",
    status,
    ...extra,
  };
}

const live = fmt("live", "active", { tournament_count: 992, deck_count: 13422 });
const up = fmt("up", "upcoming");
const old = fmt("old", "frozen", { tournament_count: 430, deck_count: 3000 });

describe("HomeFormatSections", () => {
  it("puts active and upcoming formats in the active section", () => {
    render(<HomeFormatSections formats={[live, up, old]} />);
    const active = screen.getByRole("region", { name: "Active formats" });
    expect(within(active).getByText("Live")).toBeDefined();
    expect(within(active).getByText("Up")).toBeDefined();
    expect(within(active).queryByText("Old")).toBeNull();
  });

  it("lists frozen formats as links in the archive section", () => {
    render(<HomeFormatSections formats={[live, up, old]} />);
    const archive = screen.getByRole("region", { name: "Archived formats" });
    const link = within(archive).getByRole("link");
    expect(link.getAttribute("href")).toBe("/old");
    expect(within(archive).getByText("430 tournaments")).toBeDefined();
  });

  it("does not link upcoming formats", () => {
    render(<HomeFormatSections formats={[live, up, old]} />);
    expect(screen.queryByRole("link", { name: /Up/ })).toBeNull();
    expect(screen.getByRole("link", { name: /Live/ }).getAttribute("href")).toBe("/live");
  });

  it("hides the archive section when no format is frozen", () => {
    render(<HomeFormatSections formats={[live, up]} />);
    expect(screen.queryByRole("region", { name: "Archived formats" })).toBeNull();
  });

  it("shows an empty state when no format is active or upcoming", () => {
    render(<HomeFormatSections formats={[old]} />);
    const active = screen.getByRole("region", { name: "Active formats" });
    expect(within(active).getByText("No active formats right now.")).toBeDefined();
  });

  it("shows 0 tournaments when the count is missing", () => {
    render(<HomeFormatSections formats={[fmt("bare", "frozen")]} />);
    const archive = screen.getByRole("region", { name: "Archived formats" });
    expect(within(archive).getByText("0 tournaments")).toBeDefined();
  });

  it("uses the singular for one tournament and one deck", () => {
    render(<HomeFormatSections formats={[fmt("tiny", "frozen", { tournament_count: 1, deck_count: 1 })]} />);
    const archive = screen.getByRole("region", { name: "Archived formats" });
    expect(within(archive).getByText("1 tournament")).toBeDefined();
    expect(within(archive).getByText("1 deck")).toBeDefined();
  });
});
