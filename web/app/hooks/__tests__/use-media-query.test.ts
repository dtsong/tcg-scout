import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, cleanup } from "@testing-library/react";
import { useMediaQuery } from "../use-media-query";

type ChangeHandler = (e: MediaQueryListEvent) => void;

function createMockMatchMedia(initialMatches: boolean) {
  let handler: ChangeHandler | null = null;
  const mql = {
    matches: initialMatches,
    media: "",
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn((_event: string, cb: ChangeHandler) => {
      handler = cb;
    }),
    removeEventListener: vi.fn((_event: string, cb: ChangeHandler) => {
      if (handler === cb) handler = null;
    }),
    dispatchEvent: () => false,
  };

  function fireChange(matches: boolean) {
    mql.matches = matches;
    if (handler) handler({ matches } as MediaQueryListEvent);
  }

  return { mql, fireChange };
}

describe("useMediaQuery", () => {
  const originalMatchMedia = window.matchMedia;

  afterEach(() => {
    cleanup();
    window.matchMedia = originalMatchMedia;
  });

  it("returns false initially (SSR-safe default)", () => {
    const { mql } = createMockMatchMedia(false);
    window.matchMedia = vi.fn(() => mql as unknown as MediaQueryList);

    const { result } = renderHook(() => useMediaQuery("(max-width: 640px)"));
    expect(result.current).toBe(false);
  });

  it("reads mq.matches on mount and updates state", () => {
    const { mql } = createMockMatchMedia(true);
    window.matchMedia = vi.fn(() => mql as unknown as MediaQueryList);

    const { result } = renderHook(() => useMediaQuery("(max-width: 640px)"));
    expect(result.current).toBe(true);
  });

  it("responds to change events", () => {
    const { mql, fireChange } = createMockMatchMedia(false);
    window.matchMedia = vi.fn(() => mql as unknown as MediaQueryList);

    const { result } = renderHook(() => useMediaQuery("(max-width: 640px)"));
    expect(result.current).toBe(false);

    act(() => fireChange(true));
    expect(result.current).toBe(true);

    act(() => fireChange(false));
    expect(result.current).toBe(false);
  });

  it("cleans up event listener on unmount", () => {
    const { mql } = createMockMatchMedia(false);
    window.matchMedia = vi.fn(() => mql as unknown as MediaQueryList);

    const { unmount } = renderHook(() => useMediaQuery("(max-width: 640px)"));
    expect(mql.addEventListener).toHaveBeenCalledWith("change", expect.any(Function));

    unmount();
    expect(mql.removeEventListener).toHaveBeenCalledWith("change", expect.any(Function));
  });

  it("re-subscribes when the query argument changes", () => {
    const mock1 = createMockMatchMedia(false);
    const mock2 = createMockMatchMedia(true);
    let callCount = 0;

    window.matchMedia = vi.fn(() => {
      callCount++;
      return (callCount === 1 ? mock1.mql : mock2.mql) as unknown as MediaQueryList;
    });

    const { result, rerender } = renderHook(
      ({ query }: { query: string }) => useMediaQuery(query),
      { initialProps: { query: "(max-width: 640px)" } },
    );
    expect(result.current).toBe(false);

    rerender({ query: "(max-width: 768px)" });
    expect(result.current).toBe(true);
    expect(mock1.mql.removeEventListener).toHaveBeenCalled();
  });
});
