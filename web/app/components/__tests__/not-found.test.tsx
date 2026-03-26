import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import NotFound from "@/app/not-found";

describe("NotFound page", () => {
  afterEach(cleanup);

  it("renders the heading and link back to homepage", () => {
    render(<NotFound />);
    expect(screen.getByText("Page not found")).toBeInTheDocument();
    const link = screen.getByText("Back to Scout");
    expect(link).toHaveAttribute("href", "/");
  });
});
