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
    region: "jp",
    ...extra,
  };
}

const live = fmt("live", "active", { tournament_count: 992, deck_count: 13422 });
const up = fmt("up", "upcoming");
const old = fmt("old", "frozen", { tournament_count: 430, deck_count: 3000 });
const season = fmt("season", "active", {
  region: "tpci",
  dataset_start: "2026-09-05",
  dataset_end: "2027-09-03",
  tournament_count: 11,
  deck_count: 20273,
});
const lastSeason = fmt("lastseason", "frozen", { region: "tpci", tournament_count: 39, deck_count: 55417 });

const jpRegion = () => screen.getByRole("region", { name: "Japan City League" });
const tpciRegion = () => screen.getByRole("region", { name: "International (TPCi)" });

describe("HomeFormatSections", () => {
  it("lists each circuit in its own section", () => {
    render(<HomeFormatSections formats={[live, up, old, season, lastSeason]} />);
    expect(within(jpRegion()).getByText("Live")).toBeDefined();
    expect(within(jpRegion()).getByText("Old")).toBeDefined();
    expect(within(jpRegion()).queryByText("Season")).toBeNull();
    expect(within(tpciRegion()).getByText("Season")).toBeDefined();
    expect(within(tpciRegion()).getByText("Lastseason")).toBeDefined();
  });

  it("puts a format without a region under Japan City League", () => {
    render(<HomeFormatSections formats={[fmt("legacy", "active", { region: undefined })]} />);
    expect(within(jpRegion()).getByText("Legacy")).toBeDefined();
  });

  it("hides a circuit that has no formats", () => {
    render(<HomeFormatSections formats={[live]} />);
    expect(screen.queryByRole("region", { name: "International (TPCi)" })).toBeNull();
  });

  it("lists frozen formats as links in the circuit's archive", () => {
    render(<HomeFormatSections formats={[live, old]} />);
    const archive = within(jpRegion()).getByRole("list", { name: "Archived formats" });
    expect(within(archive).getByRole("link").getAttribute("href")).toBe("/old");
    expect(within(archive).getByText("430 tournaments")).toBeDefined();
  });

  it("hides the archive list when a circuit has no frozen formats", () => {
    render(<HomeFormatSections formats={[live, up]} />);
    expect(within(jpRegion()).queryByRole("list", { name: "Archived formats" })).toBeNull();
  });

  it("does not link upcoming formats", () => {
    render(<HomeFormatSections formats={[live, up]} />);
    expect(screen.queryByRole("link", { name: /Up/ })).toBeNull();
    expect(screen.getByRole("link", { name: /Live/ }).getAttribute("href")).toBe("/live");
  });

  it("says so when a circuit has no current format", () => {
    render(<HomeFormatSections formats={[old]} />);
    expect(within(jpRegion()).getByText(/No current format/)).toBeDefined();
  });

  it("shows a JP format's full legal window", () => {
    render(<HomeFormatSections formats={[live]} />);
    expect(within(jpRegion()).getByText("Active")).toBeDefined();
    expect(within(jpRegion()).getByText(/Legal Jun 5, 2026 to Aug 13, 2026/)).toBeDefined();
  });

  it("marks the TPCi season as current and shows only its start date", () => {
    render(<HomeFormatSections formats={[season]} />);
    expect(within(tpciRegion()).getByText("Current season")).toBeDefined();
    expect(within(tpciRegion()).getByText(/Legal from Sep 5, 2026/)).toBeDefined();
    expect(within(tpciRegion()).queryByText(/2027/)).toBeNull();
  });

  it("explains that an active format has no results yet", () => {
    render(<HomeFormatSections formats={[fmt("fresh", "active")]} />);
    expect(screen.getByText(/No results yet/)).toBeDefined();
  });

  it("shows 0 tournaments when the count is missing", () => {
    render(<HomeFormatSections formats={[fmt("bare", "frozen")]} />);
    expect(within(jpRegion()).getByText("0 tournaments")).toBeDefined();
  });

  it("uses the singular for one tournament and one deck", () => {
    render(<HomeFormatSections formats={[fmt("tiny", "frozen", { tournament_count: 1, deck_count: 1 })]} />);
    expect(within(jpRegion()).getByText("1 tournament")).toBeDefined();
    expect(within(jpRegion()).getByText("1 deck")).toBeDefined();
  });
});
