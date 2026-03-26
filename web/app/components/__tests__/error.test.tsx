import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ErrorPage from "@/app/error";

function makeError(message = "test failure"): Error & { digest?: string } {
  return Object.assign(new globalThis.Error(message), { digest: undefined });
}

describe("Error boundary", () => {
  afterEach(cleanup);

  it("renders the error heading and action buttons", () => {
    const reset = vi.fn();
    render(<ErrorPage error={makeError()} reset={reset} />);
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByText("Try again")).toBeInTheDocument();
    expect(screen.getByText("Back to Scout")).toBeInTheDocument();
  });

  it("calls reset when Try again is clicked", async () => {
    const user = userEvent.setup();
    const reset = vi.fn();
    render(<ErrorPage error={makeError()} reset={reset} />);
    await user.click(screen.getByText("Try again"));
    expect(reset).toHaveBeenCalledOnce();
  });

  it("displays error digest when present", () => {
    const reset = vi.fn();
    const error = Object.assign(new globalThis.Error("server error"), { digest: "abc123" });
    render(<ErrorPage error={error} reset={reset} />);
    expect(screen.getByText("Reference: abc123")).toBeInTheDocument();
  });

  it("hides digest when not present", () => {
    const reset = vi.fn();
    render(<ErrorPage error={makeError()} reset={reset} />);
    expect(screen.queryByText(/Reference:/)).not.toBeInTheDocument();
  });

  it("links back to the homepage", () => {
    const reset = vi.fn();
    render(<ErrorPage error={makeError()} reset={reset} />);
    const link = screen.getByText("Back to Scout");
    expect(link).toHaveAttribute("href", "/");
  });
});
