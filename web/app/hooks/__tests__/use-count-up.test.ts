import { describe, it, expect, afterEach, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useCountUp } from "../use-count-up";

let rafId = 0;
let callbacks: Array<{ id: number; cb: FrameRequestCallback }> = [];

beforeEach(() => {
  vi.useFakeTimers();
  rafId = 0;
  callbacks = [];
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    const id = ++rafId;
    callbacks.push({ id, cb });
    return id;
  });
  vi.stubGlobal("cancelAnimationFrame", vi.fn());
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

function driveAnimation(startTime: number) {
  const steps = [0, 100, 200, 300, 400, 500, 600, 700];
  for (const offset of steps) {
    const pending = [...callbacks];
    callbacks.length = 0;
    for (const { cb } of pending) {
      act(() => cb(startTime + offset));
    }
  }
}

describe("useCountUp", () => {
  it("uses target as initial value for hydration safety", () => {
    // useState(target) ensures SSR HTML matches client initial render
    // The value changes to 0 once the mount effect fires and animation begins
    const { result } = renderHook(() => useCountUp(100));
    // After mount effect: value is 0 (animation starting)
    expect(result.current).toBe(0);
  });

  it("animates from 0 to target on mount", () => {
    const { result } = renderHook(() => useCountUp(200));

    // Should start at 0 after mount effect
    expect(result.current).toBe(0);

    // Drive animation frames to completion
    driveAnimation(performance.now());

    expect(result.current).toBe(200);
  });

  it("animates from 0 to target when target changes", () => {
    const { result, rerender } = renderHook(
      ({ target }) => useCountUp(target),
      { initialProps: { target: 100 } },
    );

    // Complete initial animation
    driveAnimation(performance.now());
    expect(result.current).toBe(100);

    // Change target to trigger new animation
    rerender({ target: 300 });

    // Value resets to 0
    expect(result.current).toBe(0);

    // Complete second animation
    driveAnimation(performance.now());
    expect(result.current).toBe(300);
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

    // With reduced motion, effect sets target directly without animation
    expect(result.current).toBe(500);
    // No RAF callbacks should have been queued
    expect(callbacks).toHaveLength(0);
  });

  it("handles decimals parameter", () => {
    const { result } = renderHook(() => useCountUp(9.87, 2));

    // Drive animation to completion
    driveAnimation(performance.now());

    expect(result.current).toBe(9.87);
  });
});
