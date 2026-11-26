import { describe, it, expect } from "vitest";
import type { FormatInfo } from "../types";
import { formatRegion, groupFormatsByRegion } from "../format-regions";

function fmt(slug: string, region?: FormatInfo["region"]): FormatInfo {
  return {
    slug,
    name: slug,
    name_en: slug,
    description: "",
    dataset_start: "2026-01-01",
    dataset_end: "2026-02-01",
    status: "active",
    ...(region ? { region } : {}),
  };
}

describe("formatRegion", () => {
  it("treats a format without a region as Japan City League", () => {
    expect(formatRegion(fmt("old-json"))).toBe("jp");
  });
});

describe("groupFormatsByRegion", () => {
  it("puts Japan City League first, then TPCi, and keeps the input order", () => {
    const groups = groupFormatsByRegion([fmt("t1", "tpci"), fmt("j1", "jp"), fmt("t2", "tpci"), fmt("j2")]);
    expect(groups.map((g) => g.label)).toEqual(["Japan City League", "International (TPCi)"]);
    expect(groups.map((g) => g.formats.map((f) => f.slug))).toEqual([["j1", "j2"], ["t1", "t2"]]);
  });

  it("drops a circuit with no formats", () => {
    expect(groupFormatsByRegion([fmt("j1", "jp")]).map((g) => g.region)).toEqual(["jp"]);
  });
});
