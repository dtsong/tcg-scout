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
  it("returns 0 initially", () => {
    const { result } = renderHook(() => useCountUp(100));
    expect(result.current).toBe(0);
  });

  it("returns target value after animation completes", () => {
    let rafId = 0;
    const callbacks: Array<{ id: number; cb: FrameRequestCallback }> = [];

    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      const id = ++rafId;
      callbacks.push({ id, cb });
      return id;
    });
    vi.stubGlobal("cancelAnimationFrame", vi.fn());

    const { result } = renderHook(() => useCountUp(200));

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

    // The first useEffect sets reducedMotion, the second reads it.
    // Both run synchronously during renderHook, so the value should be set.
    expect(result.current).toBe(500);
  });
});
