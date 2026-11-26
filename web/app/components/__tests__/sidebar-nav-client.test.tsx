import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, within } from "@testing-library/react";

const mockPathname = vi.fn().mockReturnValue("/tpci-standard");
vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname(),
}));

import { SidebarNavClient } from "../sidebar-nav-client";
import type { FormatInfo } from "@/app/lib/types";

afterEach(cleanup);

function fmt(slug: string, status: FormatInfo["status"], region?: FormatInfo["region"]): FormatInfo {
  return {
    slug,
    name: slug,
    name_en: slug,
    description: "",
    dataset_start: "2025-01-01",
    dataset_end: "2025-09-11",
    status,
    tournament_count: 1,
    deck_count: 1,
    generated_at: "",
    ...(region ? { region } : {}),
  };
}

describe("SidebarNavClient format switcher", () => {
  const jpGroup = () => screen.getByRole("group", { name: "Japan City League" });
  const tpciGroup = () => screen.getByRole("group", { name: "International (TPCi)" });

  it("lists each circuit's formats under its own heading", () => {
    const formats = [fmt("storm-emeralda", "active", "jp"), fmt("tpci-standard-2027", "active", "tpci")];
    render(<SidebarNavClient format="storm-emeralda" formats={formats} />);

    expect(within(jpGroup()).getByRole("link", { name: "storm-emeralda" })).toBeDefined();
    expect(within(jpGroup()).queryByRole("link", { name: "tpci-standard-2027" })).toBeNull();
    expect(within(tpciGroup()).getByRole("link", { name: "tpci-standard-2027" })).toBeDefined();
  });

  it("puts a format without a region under Japan City League", () => {
    const formats = [fmt("legacy", "active"), fmt("tpci-standard-2027", "active", "tpci")];
    render(<SidebarNavClient format="legacy" formats={formats} />);

    expect(within(jpGroup()).getByRole("link", { name: "legacy" })).toBeDefined();
  });

  it("lists frozen formats under the circuit's Archived formats heading", () => {
    const formats = [
      fmt("storm-emeralda", "active", "jp"),
      fmt("tpci-standard-2027", "active", "tpci"),
      fmt("tpci-standard", "frozen", "tpci"),
    ];
    render(<SidebarNavClient format="storm-emeralda" formats={formats} />);

    expect(within(tpciGroup()).getByRole("heading", { name: "Archived formats" })).toBeDefined();
    expect(within(tpciGroup()).getByRole("link", { name: "tpci-standard" })).toBeDefined();
    expect(within(jpGroup()).queryByRole("heading", { name: "Archived formats" })).toBeNull();
  });

  it("labels each format by its name, so TPCi formats show their season", () => {
    const season = {
      ...fmt("tpci-standard-2027", "active", "tpci"),
      name: "TPCi Standard 2026-27",
      name_en: "2026-27 Standard (regulation H-I-J)",
    };
    render(<SidebarNavClient format="storm-emeralda" formats={[fmt("storm-emeralda", "active", "jp"), season]} />);

    expect(within(tpciGroup()).getByRole("link", { name: "TPCi Standard 2026-27" })).toBeDefined();
  });
});
