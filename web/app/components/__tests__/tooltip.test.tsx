import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Tooltip, InfoIcon } from "../tooltip";

describe("Tooltip", () => {
  afterEach(cleanup);

  it("hides content by default", () => {
    render(
      <Tooltip content="Tip text">
        <button>Trigger</button>
      </Tooltip>,
    );
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("shows content on hover and hides on unhover", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Tip text">
        <button>Trigger</button>
      </Tooltip>,
    );

    await user.hover(screen.getByText("Trigger"));
    expect(screen.getByRole("tooltip")).toHaveTextContent("Tip text");

    await user.unhover(screen.getByText("Trigger"));
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("shows content on focus and hides on blur", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Tip text">
        <button>Trigger</button>
      </Tooltip>,
    );

    await user.tab();
    expect(screen.getByRole("tooltip")).toHaveTextContent("Tip text");

    await user.tab();
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("renders bottom position when trigger is near viewport top", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Tip text">
        <button>Trigger</button>
      </Tooltip>,
    );

    // jsdom returns rect.top = 0, which is < 80, so position should be "bottom"
    await user.hover(screen.getByText("Trigger"));
    const tooltip = screen.getByRole("tooltip");
    expect(tooltip.className).toContain("top-full");
  });
});

describe("InfoIcon", () => {
  afterEach(cleanup);

  it("renders the info icon with accessible attributes", () => {
    render(<InfoIcon tooltip="Help text" />);
    const icon = screen.getByRole("button", { name: "More information" });
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveAttribute("tabindex", "0");
  });

  it("shows tooltip content on hover", async () => {
    const user = userEvent.setup();
    render(<InfoIcon tooltip="Help text" />);

    await user.hover(screen.getByRole("button", { name: "More information" }));
    expect(screen.getByRole("tooltip")).toHaveTextContent("Help text");
  });
});
