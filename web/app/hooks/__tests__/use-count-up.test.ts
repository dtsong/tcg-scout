import { describe, it, expect, afterEach, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useCountUp } from "../use-count-up";

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    onchange: null,
    dispatchEvent: vi.fn(),
  }));
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("useCountUp", () => {
  it("returns target initially (avoids hydration mismatch)", () => {
    const { result } = renderHook(() => useCountUp(100));
    expect(result.current).toBe(100);
  });

  it("animates from 0 to target when target changes", () => {
    let rafId = 0;
    const callbacks: Array<{ id: number; cb: FrameRequestCallback }> = [];

    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      const id = ++rafId;
      callbacks.push({ id, cb });
      return id;
    });
    vi.stubGlobal("cancelAnimationFrame", vi.fn());

    const { result, rerender } = renderHook(
      ({ target }) => useCountUp(target),
      { initialProps: { target: 100 } },
    );

    // First render returns target (no animation)
    expect(result.current).toBe(100);

    // Change target to trigger animation
    rerender({ target: 200 });

    // Value should start at 0 (reset before animation)
    expect(result.current).toBe(0);

    // Simulate animation frames over 700ms (past the 600ms duration)
    const startTime = performance.now();
    const steps = [0, 100, 200, 300, 400, 500, 600, 700];
    for (const offset of steps) {
      const pending = [...callbacks];
      callbacks.length = 0;
      for (const { cb } of pending) {
        act(() => cb(startTime + offset));
      }
    }

    expect(result.current).toBe(200);
  });

  it("returns target immediately when target is 0", () => {
    const { result } = renderHook(() => useCountUp(0));
    expect(result.current).toBe(0);
  });

  it("returns target immediately with prefers-reduced-motion", () => {
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: query === "(prefers-reduced-motion: reduce)",
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      onchange: null,
      dispatchEvent: vi.fn(),
    }));

    const { result } = renderHook(() => useCountUp(500));

    // The consolidated useEffect checks matchMedia and returns target immediately.
    expect(result.current).toBe(500);
  });
});
