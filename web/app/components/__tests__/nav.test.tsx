import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mockPathname = vi.fn().mockReturnValue("/ninja-spinner");
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname(),
  useRouter: () => ({ push: mockPush }),
}));

import { Nav } from "../nav";
import type { FormatInfo } from "@/app/lib/types";

const formats: FormatInfo[] = [
  {
    slug: "ninja-spinner",
    name: "Ninja Spinner",
    name_en: "Ninja Spinner",
    description: "Current format",
    dataset_start: "2025-01-01",
    dataset_end: "2026-03-26",
    status: "active",
    tournament_count: 100,
    deck_count: 500,
  },
  {
    slug: "nihil-zero",
    name: "Nihil Zero",
    name_en: "Nihil Zero",
    description: "Previous format",
    dataset_start: "2024-01-01",
    dataset_end: "2025-01-01",
    status: "frozen",
    tournament_count: 430,
    deck_count: 2000,
  },
];

function renderNav() {
  return render(<Nav format="ninja-spinner" formats={formats} />);
}

describe("Nav", () => {
  beforeEach(() => {
    mockPathname.mockReturnValue("/ninja-spinner");
    mockPush.mockClear();
  });
  afterEach(cleanup);

  describe("Desktop nav rendering", () => {
    it("renders the main navigation landmark", () => {
      renderNav();
      const nav = screen.getByTestId("main-nav");
      expect(nav).toBeInTheDocument();
      expect(nav).toHaveAttribute("aria-label", "Main navigation");
    });

    it("renders Scout logo link", () => {
      renderNav();
      const logo = screen.getByRole("link", { name: /Scout/ });
      expect(logo).toHaveAttribute("href", "/");
    });

    it("renders the Dashboard link", () => {
      renderNav();
      const links = screen.getAllByRole("link", { name: "Dashboard" });
      expect(links.length).toBeGreaterThanOrEqual(1);
    });

    it("renders the Guide link", () => {
      renderNav();
      const links = screen.getAllByRole("link", { name: "Guide" });
      expect(links.length).toBeGreaterThanOrEqual(1);
    });
  });

  describe("ARIA attributes on dropdown menus", () => {
    it("dropdown trigger has aria-expanded=false initially", () => {
      renderNav();
      const triggers = screen.getAllByRole("button", { name: "Decks" });
      const desktopTrigger = triggers[0];
      expect(desktopTrigger).toHaveAttribute("aria-expanded", "false");
      expect(desktopTrigger).toHaveAttribute("aria-haspopup", "menu");
    });

    it("dropdown trigger gets aria-expanded=true when opened", async () => {
      const user = userEvent.setup();
      renderNav();
      const triggers = screen.getAllByRole("button", { name: "Decks" });
      const desktopTrigger = triggers[0];

      await user.click(desktopTrigger);

      expect(desktopTrigger).toHaveAttribute("aria-expanded", "true");
    });

    it("opened dropdown has role=menu and menuitem roles", async () => {
      const user = userEvent.setup();
      renderNav();
      const triggers = screen.getAllByRole("button", { name: "Decks" });
      await user.click(triggers[0]);

      const menu = screen.getByRole("menu", { name: "Decks" });
      expect(menu).toBeInTheDocument();

      const items = within(menu).getAllByRole("menuitem");
      expect(items.length).toBe(3);
    });

    it("format switcher has aria-expanded and aria-haspopup", () => {
      renderNav();
      const formatBtns = screen.getAllByRole("button", { name: /Ninja Spinner/i });
      const desktopFormatBtn = formatBtns[0];
      expect(desktopFormatBtn).toHaveAttribute("aria-expanded", "false");
      expect(desktopFormatBtn).toHaveAttribute("aria-haspopup", "menu");
    });

    it("format switcher opens with role=menu", async () => {
      const user = userEvent.setup();
      renderNav();
      const formatBtns = screen.getAllByRole("button", { name: /Ninja Spinner/i });
      await user.click(formatBtns[0]);

      const menu = screen.getByRole("menu", { name: "Format switcher" });
      expect(menu).toBeInTheDocument();
      const items = within(menu).getAllByRole("menuitem");
      expect(items.length).toBe(2);
    });
  });

  describe("Keyboard navigation", () => {
    it("Escape closes an open dropdown", async () => {
      const user = userEvent.setup();
      renderNav();
      const triggers = screen.getAllByRole("button", { name: "Decks" });
      const trigger = triggers[0];

      await user.click(trigger);
      expect(trigger).toHaveAttribute("aria-expanded", "true");

      await user.keyboard("{Escape}");
      expect(trigger).toHaveAttribute("aria-expanded", "false");
    });

    it("Escape closes format switcher", async () => {
      const user = userEvent.setup();
      renderNav();
      const formatBtns = screen.getAllByRole("button", { name: /Ninja Spinner/i });
      const formatBtn = formatBtns[0];

      await user.click(formatBtn);
      expect(formatBtn).toHaveAttribute("aria-expanded", "true");

      await user.keyboard("{Escape}");
      expect(formatBtn).toHaveAttribute("aria-expanded", "false");
    });
  });

  describe("Mobile hamburger menu", () => {
    it("renders a hamburger button visible on mobile", () => {
      renderNav();
      const hamburger = screen.getByRole("button", { name: "Open menu" });
      expect(hamburger).toBeInTheDocument();
      expect(hamburger).toHaveAttribute("aria-expanded", "false");
    });

    it("opens drawer on hamburger click", async () => {
      const user = userEvent.setup();
      renderNav();

      await user.click(screen.getByRole("button", { name: "Open menu" }));

      const drawer = screen.getByRole("dialog", { name: "Navigation menu" });
      expect(drawer).toBeInTheDocument();
      expect(drawer).toHaveAttribute("aria-modal", "true");
    });

    it("drawer contains close button", async () => {
      const user = userEvent.setup();
      renderNav();

      await user.click(screen.getByRole("button", { name: "Open menu" }));

      const closeBtn = screen.getByRole("button", { name: "Close menu" });
      expect(closeBtn).toBeInTheDocument();
    });

    it("close button closes the drawer", async () => {
      const user = userEvent.setup();
      renderNav();

      await user.click(screen.getByRole("button", { name: "Open menu" }));
      const hamburger = screen.getByRole("button", { name: "Open menu" });

      await user.click(screen.getByRole("button", { name: "Close menu" }));

      expect(hamburger).toHaveAttribute("aria-expanded", "false");
    });

    it("Escape closes the drawer", async () => {
      const user = userEvent.setup();
      renderNav();

      await user.click(screen.getByRole("button", { name: "Open menu" }));
      expect(
        screen.getByRole("button", { name: "Open menu" }),
      ).toHaveAttribute("aria-expanded", "true");

      await user.keyboard("{Escape}");

      expect(
        screen.getByRole("button", { name: "Open menu" }),
      ).toHaveAttribute("aria-expanded", "false");
    });

    it("mobile nav groups expand on click with ARIA", async () => {
      const user = userEvent.setup();
      renderNav();

      await user.click(screen.getByRole("button", { name: "Open menu" }));

      const drawer = screen.getByRole("dialog");
      const decksBtn = within(drawer).getByRole("button", { name: "Decks" });
      expect(decksBtn).toHaveAttribute("aria-expanded", "false");
      expect(decksBtn).toHaveAttribute("aria-haspopup", "menu");

      await user.click(decksBtn);
      expect(decksBtn).toHaveAttribute("aria-expanded", "true");
    });

    it("locks body scroll when drawer is open", async () => {
      const user = userEvent.setup();
      renderNav();

      await user.click(screen.getByRole("button", { name: "Open menu" }));
      expect(document.body.style.overflow).toBe("hidden");

      await user.click(screen.getByRole("button", { name: "Close menu" }));
      expect(document.body.style.overflow).toBe("");
    });
  });

  describe("Touch target sizes", () => {
    it("hamburger button has min 44px touch target", () => {
      renderNav();
      const hamburger = screen.getByRole("button", { name: "Open menu" });
      expect(hamburger.className).toContain("min-h-11");
      expect(hamburger.className).toContain("min-w-11");
    });

    it("dropdown triggers have min 44px height", () => {
      renderNav();
      const triggers = screen.getAllByRole("button", { name: "Decks" });
      expect(triggers[0].className).toContain("min-h-11");
      expect(triggers[0].className).toContain("min-w-11");
    });

    it("desktop nav links have min 44px height", () => {
      renderNav();
      const links = screen.getAllByRole("link", { name: "Dashboard" });
      const desktopLink = links.find((l) => l.className.includes("min-h-11"));
      expect(desktopLink).toBeTruthy();
    });
  });
});
