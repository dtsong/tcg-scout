import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

const mockPathname = vi.fn().mockReturnValue("/tpci-standard");
vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname(),
}));

import { SidebarNavClient } from "../sidebar-nav-client";
import type { FormatInfo } from "@/app/lib/types";

afterEach(cleanup);

function fmt(slug: string, status: FormatInfo["status"]): FormatInfo {
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
  };
}

describe("SidebarNavClient format switcher", () => {
  it("groups frozen formats under a separate Archives heading", () => {
    const formats = [fmt("tpci-standard", "active"), fmt("tpci-standard-2025", "frozen")];
    render(<SidebarNavClient format="tpci-standard" formats={formats} />);

    expect(screen.getByRole("heading", { name: /archives/i })).toBeDefined();
    expect(screen.getByRole("link", { name: /tpci-standard-2025/i })).toBeDefined();
  });

  it("omits the Archives heading when no frozen formats exist", () => {
    const formats = [fmt("tpci-standard", "active"), fmt("abyss-eye", "upcoming")];
    render(<SidebarNavClient format="tpci-standard" formats={formats} />);

    expect(screen.queryByRole("heading", { name: /archives/i })).toBeNull();
  });
});
