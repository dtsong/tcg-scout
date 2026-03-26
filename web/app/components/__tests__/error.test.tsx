import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ErrorPage from "@/app/error";

describe("Error boundary", () => {
  afterEach(cleanup);

  it("renders the error heading and action buttons", () => {
    const reset = vi.fn();
    render(<ErrorPage error={Object.assign(new globalThis.Error("test failure"), { digest: undefined })} reset={reset} />);
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByText("Try again")).toBeInTheDocument();
    expect(screen.getByText("Back to Scout")).toBeInTheDocument();
  });

  it("calls reset when Try again is clicked", async () => {
    const user = userEvent.setup();
    const reset = vi.fn();
    render(<ErrorPage error={Object.assign(new globalThis.Error("test failure"), { digest: undefined })} reset={reset} />);
    await user.click(screen.getByText("Try again"));
    expect(reset).toHaveBeenCalledOnce();
  });

  it("links back to the homepage", () => {
    const reset = vi.fn();
    render(<ErrorPage error={Object.assign(new globalThis.Error("test failure"), { digest: undefined })} reset={reset} />);
    const link = screen.getByText("Back to Scout");
    expect(link).toHaveAttribute("href", "/");
  });
});
