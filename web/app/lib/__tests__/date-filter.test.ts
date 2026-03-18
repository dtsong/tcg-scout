import { describe, it, expect } from "vitest";
import { filterByDateRange } from "../../components/date-filter-provider";

describe("filterByDateRange", () => {
  const items = [
    { name: "Event 1", date: "2026-01-10" },
    { name: "Event 2", date: "2026-02-15" },
    { name: "Event 3", date: "2026-03-01" },
    { name: "Event 4", date: "2026-03-10" },
  ];

  it("filters items within range", () => {
    const result = filterByDateRange(items, "date", {
      start: "2026-02-01",
      end: "2026-03-05",
    });
    expect(result).toHaveLength(2);
    expect(result[0].name).toBe("Event 2");
    expect(result[1].name).toBe("Event 3");
  });

  it("returns all items when range covers everything", () => {
    const result = filterByDateRange(items, "date", {
      start: "2026-01-01",
      end: "2026-12-31",
    });
    expect(result).toHaveLength(4);
  });

  it("returns empty array when no items in range", () => {
    const result = filterByDateRange(items, "date", {
      start: "2025-01-01",
      end: "2025-12-31",
    });
    expect(result).toHaveLength(0);
  });

  it("includes items on boundary dates", () => {
    const result = filterByDateRange(items, "date", {
      start: "2026-01-10",
      end: "2026-01-10",
    });
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("Event 1");
  });
});
