import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CardLink } from "../card-link";

describe("CardLink", () => {
  afterEach(cleanup);

  it("renders link with correct href from slugified name", () => {
    render(<CardLink name="Boss's Orders" format="nihil-zero" />);
    const link = screen.getByRole("link", { name: "Boss's Orders" });
    expect(link).toHaveAttribute("href", "/nihil-zero/cards/boss-s-orders");
  });

  it("applies default className when none provided", () => {
    render(<CardLink name="Rare Candy" format="ninja-spinner" />);
    const link = screen.getByRole("link", { name: "Rare Candy" });
    expect(link.className).toContain("hover:text-accent");
  });

  it("applies custom className when provided", () => {
    render(<CardLink name="Prime Catcher" format="nihil-zero" className="text-slate-200 hover:text-accent" />);
    const link = screen.getByRole("link", { name: "Prime Catcher" });
    expect(link.className).toContain("text-slate-200");
  });

  it("stops event propagation on click", async () => {
    const parentHandler = vi.fn();
    const user = userEvent.setup();
    render(
      <div onClick={parentHandler}>
        <CardLink name="Nest Ball" format="nihil-zero" />
      </div>,
    );
    await user.click(screen.getByRole("link", { name: "Nest Ball" }));
    expect(parentHandler).not.toHaveBeenCalled();
  });
});
