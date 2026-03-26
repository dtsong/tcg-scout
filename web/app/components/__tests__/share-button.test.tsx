import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ShareButton } from "../share-button";

// Mock analytics
vi.mock("@/app/lib/analytics", () => ({
  trackEvent: vi.fn(),
}));

import { trackEvent } from "@/app/lib/analytics";

// Suppress navigator.share by default (desktop behavior)
const originalNavigator = { ...navigator };

beforeEach(() => {
  vi.clearAllMocks();
  // Ensure no Web Share API by default
  Object.defineProperty(window, "navigator", {
    value: { ...originalNavigator, share: undefined, clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } },
    writable: true,
    configurable: true,
  });
});

afterEach(cleanup);

describe("ShareButton", () => {
  it("renders share button with label", () => {
    render(<ShareButton title="Test" pageType="archetype" />);
    expect(screen.getByRole("button", { name: /share/i })).toBeDefined();
  });

  it("opens dropdown menu on click (desktop, no Web Share API)", async () => {
    const user = userEvent.setup();
    render(<ShareButton title="Test" pageType="archetype" />);

    await user.click(screen.getByRole("button", { name: /share/i }));

    expect(screen.getByRole("menu")).toBeDefined();
    expect(screen.getByText("Copy Link")).toBeDefined();
    expect(screen.getByText("Share on X")).toBeDefined();
  });

  it("copies link to clipboard and tracks analytics", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(window, "navigator", {
      value: { ...originalNavigator, share: undefined, clipboard: { writeText } },
      writable: true,
      configurable: true,
    });

    render(<ShareButton title="Test" pageType="archetype" url="https://scout.trainerlab.io/test" />);

    await user.click(screen.getByRole("button", { name: /share/i }));
    await user.click(screen.getByText("Copy Link"));

    expect(writeText).toHaveBeenCalledWith("https://scout.trainerlab.io/test");
    expect(trackEvent).toHaveBeenCalledWith("share_click", {
      method: "copy-link",
      page_type: "archetype",
    });
    expect(trackEvent).toHaveBeenCalledWith("copy_link", {
      page_type: "archetype",
    });
    expect(screen.getByText("Copied!")).toBeDefined();
  });

  it("opens Twitter intent URL on Share on X click", async () => {
    const user = userEvent.setup();
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);

    render(
      <ShareButton
        title="Charizard ex - Scout"
        text="Charizard ex (S tier)"
        pageType="archetype"
        url="https://scout.trainerlab.io/charizard"
      />,
    );

    await user.click(screen.getByRole("button", { name: /share/i }));
    await user.click(screen.getByText("Share on X"));

    expect(openSpy).toHaveBeenCalledWith(
      expect.stringContaining("twitter.com/intent/tweet"),
      "_blank",
      "noopener,noreferrer",
    );
    expect(openSpy).toHaveBeenCalledWith(
      expect.stringContaining("Charizard"),
      "_blank",
      "noopener,noreferrer",
    );
    expect(trackEvent).toHaveBeenCalledWith("share_click", {
      method: "twitter",
      page_type: "archetype",
    });

    openSpy.mockRestore();
  });

  it("uses Web Share API when available on mobile", async () => {
    const user = userEvent.setup();
    const shareFn = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(window, "navigator", {
      value: { ...originalNavigator, share: shareFn, clipboard: { writeText: vi.fn() } },
      writable: true,
      configurable: true,
    });

    render(
      <ShareButton
        title="Dashboard - Scout"
        text="Meta dashboard"
        pageType="dashboard"
        url="https://scout.trainerlab.io/ninja-spinner"
      />,
    );

    await user.click(screen.getByRole("button", { name: /share/i }));

    expect(shareFn).toHaveBeenCalledWith({
      title: "Dashboard - Scout",
      text: "Meta dashboard",
      url: "https://scout.trainerlab.io/ninja-spinner",
    });
    expect(trackEvent).toHaveBeenCalledWith("share_click", {
      method: "web-share",
      page_type: "dashboard",
    });
  });

  it("closes dropdown on Escape key", async () => {
    const user = userEvent.setup();
    render(<ShareButton title="Test" pageType="dashboard" />);

    await user.click(screen.getByRole("button", { name: /share/i }));
    expect(screen.getByRole("menu")).toBeDefined();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("closes dropdown on click outside", async () => {
    const user = userEvent.setup();
    render(
      <div>
        <span data-testid="outside">outside</span>
        <ShareButton title="Test" pageType="dashboard" />
      </div>,
    );

    await user.click(screen.getByRole("button", { name: /share/i }));
    expect(screen.getByRole("menu")).toBeDefined();

    await user.click(screen.getByTestId("outside"));
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("does not open dropdown when user cancels Web Share (AbortError)", async () => {
    const user = userEvent.setup();
    const abortError = new DOMException("Share cancelled", "AbortError");
    const shareFn = vi.fn().mockRejectedValue(abortError);
    Object.defineProperty(window, "navigator", {
      value: { ...originalNavigator, share: shareFn, clipboard: { writeText: vi.fn() } },
      writable: true,
      configurable: true,
    });

    render(<ShareButton title="Test" pageType="archetype" />);
    await user.click(screen.getByRole("button", { name: /share/i }));

    expect(shareFn).toHaveBeenCalled();
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("falls through to dropdown when Web Share API fails with non-abort error", async () => {
    const user = userEvent.setup();
    const shareFn = vi.fn().mockRejectedValue(new Error("NotAllowedError"));
    Object.defineProperty(window, "navigator", {
      value: { ...originalNavigator, share: shareFn, clipboard: { writeText: vi.fn() } },
      writable: true,
      configurable: true,
    });

    render(<ShareButton title="Test" pageType="archetype" />);
    await user.click(screen.getByRole("button", { name: /share/i }));

    expect(shareFn).toHaveBeenCalled();
    expect(screen.getByRole("menu")).toBeDefined();
  });

  it("closes dropdown when clipboard copy fails completely", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockRejectedValue(new Error("Clipboard blocked"));
    Object.defineProperty(window, "navigator", {
      value: { ...originalNavigator, share: undefined, clipboard: { writeText } },
      writable: true,
      configurable: true,
    });
    // Also disable execCommand fallback
    document.execCommand = vi.fn().mockReturnValue(false);

    render(<ShareButton title="Test" pageType="archetype" url="https://example.com" />);

    await user.click(screen.getByRole("button", { name: /share/i }));
    expect(screen.getByRole("menu")).toBeDefined();

    await user.click(screen.getByText("Copy Link"));
    expect(screen.queryByRole("menu")).toBeNull();
    expect(trackEvent).not.toHaveBeenCalled();
  });

  it("has correct ARIA attributes", () => {
    render(<ShareButton title="Test" pageType="archetype" />);
    const button = screen.getByRole("button", { name: /share/i });
    expect(button.getAttribute("aria-haspopup")).toBe("menu");
    expect(button.getAttribute("aria-expanded")).toBe("false");
  });
});
