import { describe, it, expect, vi } from "vitest";
import { render, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Tabs } from "../tabs";

const tabs = [
  { id: "overview", label: "Overview" },
  { id: "decklist", label: "Decklist" },
  { id: "matchups", label: "Matchups" },
];

describe("Tabs", () => {
  it("renders all tab labels", () => {
    const { container } = render(
      <Tabs tabs={tabs} activeTab="overview" onTabChange={() => {}} />,
    );
    const scope = within(container);
    expect(scope.getByText("Overview")).toBeInTheDocument();
    expect(scope.getByText("Decklist")).toBeInTheDocument();
    expect(scope.getByText("Matchups")).toBeInTheDocument();
  });

  it("highlights the active tab", () => {
    const { container } = render(
      <Tabs tabs={tabs} activeTab="decklist" onTabChange={() => {}} />,
    );
    const scope = within(container);
    const activeBtn = scope.getByText("Decklist");
    expect(activeBtn.className).toContain("bg-surface-600");
    const inactiveBtn = scope.getByText("Overview");
    expect(inactiveBtn.className).not.toContain("bg-surface-600 ");
  });

  it("calls onTabChange when a tab is clicked", async () => {
    const onChange = vi.fn();
    const { container } = render(
      <Tabs tabs={tabs} activeTab="overview" onTabChange={onChange} />,
    );
    const scope = within(container);
    await userEvent.click(scope.getByText("Matchups"));
    expect(onChange).toHaveBeenCalledWith("matchups");
  });
});
