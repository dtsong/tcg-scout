import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { MetaTicker } from "../meta-ticker";

vi.mock("@/app/hooks/use-count-up", () => ({
  useCountUp: (target: number) => target,
}));

afterEach(cleanup);

describe("MetaTicker", () => {
  const baseProps = {
    formatName: "Ninja Spinner",
    tournamentCount: 430,
    deckCount: 12500,
    generatedAt: new Date().toISOString(),
  };

  it("renders format name, tournament count, and deck count", () => {
    render(<MetaTicker {...baseProps} />);
    expect(screen.getByText("Ninja Spinner")).toBeDefined();
    expect(screen.getByText("430")).toBeDefined();
    expect(screen.getByText("12,500")).toBeDefined();
    expect(screen.getByText("tournaments")).toBeDefined();
    expect(screen.getByText("decks")).toBeDefined();
  });

  it("renders 'Updated <time> ago' with a valid date", () => {
    const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString();
    render(<MetaTicker {...baseProps} generatedAt={twoHoursAgo} />);
    expect(screen.getByText("Updated 2h ago")).toBeDefined();
  });

  it("renders 'Updated Unknown' with an invalid date", () => {
    render(<MetaTicker {...baseProps} generatedAt="not-a-date" />);
    expect(screen.getByText("Updated Unknown")).toBeDefined();
  });

  it("renders rotation days when rotationDays > 0", () => {
    render(<MetaTicker {...baseProps} rotationDays={45} />);
    expect(screen.getByText("Rotation:")).toBeDefined();
    expect(screen.getByText("45d")).toBeDefined();
  });

  it("renders 'Live' when rotationDays is 0", () => {
    render(<MetaTicker {...baseProps} rotationDays={0} />);
    expect(screen.getByText("Live")).toBeDefined();
  });

  it("does not render rotation section when rotationDays is undefined", () => {
    render(<MetaTicker {...baseProps} />);
    expect(screen.queryByText("Rotation:")).toBeNull();
    expect(screen.queryByText("Live")).toBeNull();
  });
});
