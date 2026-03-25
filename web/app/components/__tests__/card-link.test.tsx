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

  it("always includes hover and transition classes", () => {
    render(<CardLink name="Rare Candy" format="ninja-spinner" />);
    const link = screen.getByRole("link", { name: "Rare Candy" });
    expect(link.className).toContain("hover:text-accent");
    expect(link.className).toContain("transition-colors");
  });

  it("merges custom className with base hover classes", () => {
    render(<CardLink name="Prime Catcher" format="nihil-zero" className="text-slate-200" />);
    const link = screen.getByRole("link", { name: "Prime Catcher" });
    expect(link.className).toContain("text-slate-200");
    expect(link.className).toContain("hover:text-accent");
  });

  it("renders plain span when name produces empty slug", () => {
    const { container } = render(<CardLink name="" format="nihil-zero" />);
    const span = container.querySelector("span");
    expect(span).not.toBeNull();
    expect(container.querySelector("a")).toBeNull();
  });

  it("renders plain span when format is empty", () => {
    render(<CardLink name="Rare Candy" format="" />);
    const span = screen.getByText("Rare Candy");
    expect(span.tagName).toBe("SPAN");
    expect(span.closest("a")).toBeNull();
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
