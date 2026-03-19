import { describe, it, expect, vi, afterEach } from "vitest";
import { formatPlacement, formatPct, daysUntil, cn, slugify } from "../utils";

describe("formatPlacement", () => {
  it("returns 1st for 1", () => {
    expect(formatPlacement(1)).toBe("1st");
  });

  it("returns 2nd for 2", () => {
    expect(formatPlacement(2)).toBe("2nd");
  });

  it("returns 3rd for 3", () => {
    expect(formatPlacement(3)).toBe("3rd");
  });

  it("returns 4th for 4", () => {
    expect(formatPlacement(4)).toBe("4th");
  });

  it("returns 11th for 11 (teen exception)", () => {
    expect(formatPlacement(11)).toBe("11th");
  });

  it("returns 21st for 21", () => {
    expect(formatPlacement(21)).toBe("21st");
  });

  it("returns em dash for null", () => {
    expect(formatPlacement(null)).toBe("—");
  });
});

describe("formatPct", () => {
  it("formats 9.0 as 9.0%", () => {
    expect(formatPct(9.0)).toBe("9.0%");
  });

  it("formats 15.5 as 15.5%", () => {
    expect(formatPct(15.5)).toBe("15.5%");
  });

  it("formats 0 as 0.0%", () => {
    expect(formatPct(0)).toBe("0.0%");
  });
});

describe("daysUntil", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns correct number of days until a future date", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
    expect(daysUntil("2026-01-11")).toBe(10);
  });

  it("returns negative days for a past date", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-11T00:00:00Z"));
    expect(daysUntil("2026-01-01")).toBeLessThan(0);
  });
});

describe("slugify", () => {
  it.each([
    ["Charizard ex", "charizard-ex"],
    ["Boss's Orders", "boss-s-orders"],
    ["raging-bolt", "raging-bolt"],
    ["Porygon-Z Box!", "porygon-z-box"],
    [" -Foo- ", "foo"],
  ])("slugifies %j to %j", (input, expected) => {
    expect(slugify(input)).toBe(expected);
  });
});

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("handles conditional classes", () => {
    expect(cn("base", false && "hidden", "visible")).toBe("base visible");
  });

  it("deduplicates tailwind classes", () => {
    const result = cn("p-4", "p-2");
    expect(result).toBe("p-2");
  });
});
