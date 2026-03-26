import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@vercel/analytics", () => ({
  track: vi.fn(),
}));

import { trackEvent } from "../analytics";
import { track } from "@vercel/analytics";

describe("trackEvent", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls track with event name", () => {
    trackEvent("share_click");
    expect(track).toHaveBeenCalledWith("share_click", undefined);
  });

  it("passes properties to track", () => {
    trackEvent("copy_link", { url: "/meta", format: "ninja-spinner" });
    expect(track).toHaveBeenCalledWith("copy_link", {
      url: "/meta",
      format: "ninja-spinner",
    });
  });

  it("calls track for each supported event type", () => {
    const events = [
      "share_click",
      "copy_link",
      "deck_save",
      "auth_signin",
    ] as const;

    for (const event of events) {
      trackEvent(event);
    }

    expect(track).toHaveBeenCalledTimes(4);
  });

  it("does not throw when track() fails", () => {
    const mockTrack = track as ReturnType<typeof vi.fn>;
    mockTrack.mockImplementation(() => {
      throw new Error("SDK init failed");
    });

    expect(() => trackEvent("share_click")).not.toThrow();
    mockTrack.mockImplementation(() => {});
  });

  it("is a no-op when window is undefined (SSR)", () => {
    const originalWindow = globalThis.window;
    // @ts-expect-error -- simulating SSR by removing window
    delete globalThis.window;

    trackEvent("share_click");
    expect(track).not.toHaveBeenCalled();

    globalThis.window = originalWindow;
  });
});
