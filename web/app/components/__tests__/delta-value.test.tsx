import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { DeltaValue } from "../delta-value";

describe("DeltaValue", () => {
  it("renders positive delta with + prefix", () => {
    const { container } = render(<DeltaValue delta={5.3} />);
    expect(container.textContent).toBe("+5.3");
  });

  it("renders negative delta", () => {
    const { container } = render(<DeltaValue delta={-2.1} />);
    expect(container.textContent).toBe("-2.1");
  });

  it("renders 0.0 for zero delta", () => {
    const { container } = render(<DeltaValue delta={0} />);
    expect(container.textContent).toBe("0.0");
  });

  it("renders -- for NaN", () => {
    const { container } = render(<DeltaValue delta={NaN} />);
    expect(container.textContent).toBe("--");
  });

  it("renders -- for Infinity", () => {
    const { container } = render(<DeltaValue delta={Infinity} />);
    expect(container.textContent).toBe("--");
  });

  it("renders -- for -Infinity", () => {
    const { container } = render(<DeltaValue delta={-Infinity} />);
    expect(container.textContent).toBe("--");
  });
});
