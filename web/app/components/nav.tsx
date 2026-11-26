"use client";

import { useState, useRef, useEffect, useCallback, useId } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn, countLabel } from "@/app/lib/utils";
import { Crosshair, ChevronDown, Menu, X } from "lucide-react";
import type { FormatInfo } from "@/app/lib/types";
import { groupFormatsByRegion } from "@/app/lib/format-regions";

interface NavGroup {
  label: string;
  items: { href: string; label: string }[];
}

/* ------------------------------------------------------------------ */
/* Keyboard helpers                                                    */
/* ------------------------------------------------------------------ */

function useMenuKeyboard(
  open: boolean,
  setOpen: (v: boolean) => void,
  containerRef: React.RefObject<HTMLElement | null>,
  triggerRef: React.RefObject<HTMLElement | null>,
  itemSelector: string,
) {
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!open) {
        if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          setOpen(true);
          return;
        }
        return;
      }

      const container = containerRef.current;
      if (!container) return;

      const items = Array.from(
        container.querySelectorAll<HTMLElement>(itemSelector),
      );
      const current = document.activeElement as HTMLElement;
      const idx = items.indexOf(current);

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          items[(idx + 1) % items.length]?.focus();
          break;
        case "ArrowUp":
          e.preventDefault();
          items[(idx - 1 + items.length) % items.length]?.focus();
          break;
        case "Escape":
          e.preventDefault();
          setOpen(false);
          triggerRef.current?.focus();
          break;
        case "Tab":
          setOpen(false);
          break;
        case "Home":
          e.preventDefault();
          items[0]?.focus();
          break;
        case "End":
          e.preventDefault();
          items[items.length - 1]?.focus();
          break;
      }
    },
    [open, setOpen, containerRef, triggerRef, itemSelector],
  );

  // Focus first item when menu opens
  useEffect(() => {
    if (open && containerRef.current) {
      const first = containerRef.current.querySelector<HTMLElement>(itemSelector);
      // Small delay so the DOM is painted
      requestAnimationFrame(() => first?.focus());
    }
  }, [open, containerRef, itemSelector]);

  return handleKeyDown;
}

/* ------------------------------------------------------------------ */
/* NavDropdown (desktop only, with ARIA)                               */
/* ------------------------------------------------------------------ */

function NavDropdown({
  group,
  pathname,
  format,
}: {
  group: NavGroup;
  pathname: string;
  format: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuId = `nav-menu-${group.label.toLowerCase()}`;

  const isGroupActive = group.items.some((item) =>
    item.href === `/${format}`
      ? pathname === `/${format}`
      : pathname.startsWith(item.href),
  );

  const handleClickOutside = useCallback(
    (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    },
    [],
  );

  useEffect(() => {
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open, handleClickOutside]);

  const handleKeyDown = useMenuKeyboard(
    open,
    setOpen,
    menuRef,
    triggerRef,
    '[role="menuitem"]',
  );

  return (
    <div className="relative" ref={ref} onKeyDown={handleKeyDown}>
      <button
        ref={triggerRef}
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-controls={open ? menuId : undefined}
        className={cn(
          "flex items-center gap-1 px-3 py-1.5 text-sm rounded-md whitespace-nowrap transition-colors min-h-11 min-w-11 justify-center",
          isGroupActive
            ? "bg-surface-600 text-slate-100"
            : "text-surface-300 hover:text-slate-200 hover:bg-surface-700",
        )}
      >
        {group.label}
        <ChevronDown
          className={cn(
            "w-3 h-3 transition-transform duration-150",
            open && "rotate-180",
          )}
        />
      </button>
      {open && (
        <div
          ref={menuRef}
          id={menuId}
          role="menu"
          aria-label={group.label}
          className="absolute top-full left-0 mt-1.5 min-w-[180px] bg-surface-700 border border-surface-500 rounded-md shadow-xl shadow-black/40 overflow-hidden z-50"
        >
          {group.items.map(({ href, label }) => {
            const active =
              href === `/${format}`
                ? pathname === `/${format}`
                : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                role="menuitem"
                tabIndex={-1}
                onClick={() => setOpen(false)}
                className={cn(
                  "block px-3 py-2 text-sm transition-colors min-h-11 flex items-center",
                  active
                    ? "bg-accent/10 text-accent"
                    : "text-slate-300 hover:bg-surface-600 hover:text-slate-100",
                )}
              >
                {label}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

function formatBadge(f: FormatInfo): string | null {
  if (f.status === "upcoming") return "Soon";
  if (f.status === "frozen") return "Complete";
  return f.region === "tpci" ? "Current season" : null;
}

/**
 * Format switcher items, grouped by circuit (Japan City League, then TPCi).
 * Shared by the desktop dropdown and the mobile drawer. Items keep
 * role="menuitem", so the menus' keyboard handling finds them through the
 * group wrappers.
 */
function FormatMenuGroups({
  formats,
  current,
  onSelect,
  itemTabIndex,
}: {
  formats: FormatInfo[];
  current: string;
  onSelect: (slug: string) => void;
  itemTabIndex?: number;
}) {
  const idPrefix = useId();
  return (
    <>
      {groupFormatsByRegion(formats).map((group, i) => {
        const labelId = `${idPrefix}-${group.region}`;
        return (
          <div
            key={group.region}
            role="group"
            aria-labelledby={labelId}
            className={cn(i > 0 && "border-t border-surface-600")}
          >
            <div id={labelId} className="px-3 pt-2.5 pb-1 text-[11px] font-medium text-surface-400">
              {group.label}
            </div>
            {group.formats.map((f) => {
              const badge = formatBadge(f);
              return (
                <button
                  key={f.slug}
                  role="menuitem"
                  tabIndex={itemTabIndex}
                  onClick={() => onSelect(f.slug)}
                  className={cn(
                    "w-full text-left px-3 py-2.5 min-h-11 transition-colors",
                    f.slug === current
                      ? "bg-accent/10 text-accent"
                      : "text-slate-300 hover:bg-surface-600 hover:text-slate-100",
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-sm font-medium">{f.name}</div>
                      {f.name_en !== f.name && (
                        <div className="text-xs text-surface-400 truncate">{f.name_en}</div>
                      )}
                    </div>
                    {badge && (
                      <span className="shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-surface-600 text-surface-400">
                        {badge}
                      </span>
                    )}
                  </div>
                  {f.tournament_count != null && f.tournament_count > 0 && (
                    <div className="text-[11px] text-surface-400 font-mono mt-0.5">
                      {countLabel(f.tournament_count, "tournament")} / {countLabel(f.deck_count, "deck")}
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        );
      })}
    </>
  );
}

/* ------------------------------------------------------------------ */
/* MobileDrawer                                                        */
/* ------------------------------------------------------------------ */

function MobileDrawer({
  open,
  onClose,
  format,
  formats,
  pathname,
  groups,
  dashboardHref,
  dashboardActive,
  matchupsHref,
  matchupsActive,
  onSwitchFormat,
}: {
  open: boolean;
  onClose: () => void;
  format: string;
  formats: FormatInfo[];
  pathname: string;
  groups: NavGroup[];
  dashboardHref: string;
  dashboardActive: boolean;
  matchupsHref: string;
  matchupsActive: boolean;
  onSwitchFormat: (slug: string) => void;
}) {
  const [expandedGroup, setExpandedGroup] = useState<string | null>(null);
  const [formatOpen, setFormatOpen] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  // Lock body scroll when open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
      // Focus close button when drawer opens
      requestAnimationFrame(() => closeRef.current?.focus());
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  // Trap focus inside drawer
  useEffect(() => {
    if (!open) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key !== "Tab" || !drawerRef.current) return;

      const focusable = drawerRef.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first?.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  // Close drawer on route change (skip initial render)
  const prevPathname = useRef(pathname);
  useEffect(() => {
    if (prevPathname.current !== pathname) {
      onClose();
      prevPathname.current = pathname;
    }
  }, [pathname, onClose]);

  const currentFormat = formats.find((f) => f.slug === format);
  const displayName = currentFormat?.name || format;

  return (
    <>
      {/* Backdrop */}
      <div
        className={cn(
          "fixed inset-0 z-[60] bg-surface-900/80 backdrop-blur-sm transition-opacity md:hidden",
          "duration-[var(--duration-normal)]",
          open
            ? "opacity-100 pointer-events-auto"
            : "opacity-0 pointer-events-none",
        )}
        aria-hidden="true"
        onClick={onClose}
      />

      {/* Drawer panel */}
      <div
        ref={drawerRef}
        id="mobile-nav-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Navigation menu"
        className={cn(
          "fixed top-0 right-0 bottom-0 z-[70] w-[280px] max-w-[85vw] bg-surface-800 border-l border-surface-600 shadow-2xl shadow-black/60 md:hidden",
          "transition-transform duration-[var(--duration-normal)] ease-[var(--ease-out)]",
          "overflow-y-auto overscroll-contain",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        {/* Drawer header */}
        <div className="flex items-center justify-between px-4 h-14 border-b border-surface-600">
          <span className="text-sm font-medium text-slate-200">Menu</span>
          <button
            ref={closeRef}
            onClick={onClose}
            aria-label="Close menu"
            className="flex items-center justify-center min-h-11 min-w-11 rounded-md text-surface-300 hover:text-slate-100 hover:bg-surface-700 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Format switcher (mobile) */}
        <div className="px-4 py-3 border-b border-surface-600">
          <button
            onClick={() => setFormatOpen((prev) => !prev)}
            aria-expanded={formatOpen}
            aria-haspopup="menu"
            className="flex items-center justify-between w-full min-h-11 text-xs font-mono px-2.5 py-1 rounded-md border bg-surface-700 border-surface-600 text-surface-300 hover:text-slate-200 hover:border-surface-500 transition-colors"
          >
            <span>{displayName}</span>
            <ChevronDown
              className={cn(
                "w-3 h-3 transition-transform duration-150",
                formatOpen && "rotate-180",
              )}
            />
          </button>
          {formatOpen && (
            <div role="menu" aria-label="Format switcher" className="mt-2 rounded-md border border-surface-500 bg-surface-700 overflow-hidden">
              <FormatMenuGroups
                formats={formats}
                current={format}
                onSelect={(slug) => {
                  setFormatOpen(false);
                  onSwitchFormat(slug);
                }}
              />
            </div>
          )}
        </div>

        {/* Nav links */}
        <nav aria-label="Mobile navigation" className="px-4 py-3">
          {/* Dashboard */}
          <Link
            href={dashboardHref}
            onClick={onClose}
            className={cn(
              "flex items-center px-3 min-h-11 text-sm rounded-md transition-colors",
              dashboardActive
                ? "bg-surface-600 text-slate-100"
                : "text-surface-300 hover:text-slate-200 hover:bg-surface-700",
            )}
          >
            Dashboard
          </Link>

          {/* Matchups */}
          <Link
            href={matchupsHref}
            onClick={onClose}
            className={cn(
              "flex items-center px-3 min-h-11 text-sm rounded-md transition-colors mt-1",
              matchupsActive
                ? "bg-surface-600 text-slate-100"
                : "text-surface-300 hover:text-slate-200 hover:bg-surface-700",
            )}
          >
            Matchups
          </Link>

          {/* Meta EV */}
          <Link
            href={`/${format}/meta-ev`}
            onClick={onClose}
            className={cn(
              "flex items-center px-3 min-h-11 text-sm rounded-md transition-colors mt-1",
              pathname.startsWith(`/${format}/meta-ev`)
                ? "bg-surface-600 text-slate-100"
                : "text-surface-300 hover:text-slate-200 hover:bg-surface-700",
            )}
          >
            Meta EV
          </Link>

          {/* Grouped nav */}
          {groups.map((group) => {
            const isExpanded = expandedGroup === group.label;
            const isGroupActive = group.items.some((item) =>
              item.href === `/${format}`
                ? pathname === `/${format}`
                : pathname.startsWith(item.href),
            );
            const groupMenuId = `mobile-menu-${group.label.toLowerCase()}`;

            return (
              <div key={group.label} className="mt-1">
                <button
                  onClick={() =>
                    setExpandedGroup(isExpanded ? null : group.label)
                  }
                  aria-expanded={isExpanded}
                  aria-haspopup="menu"
                  aria-controls={isExpanded ? groupMenuId : undefined}
                  className={cn(
                    "flex items-center justify-between w-full px-3 min-h-11 text-sm rounded-md transition-colors",
                    isGroupActive
                      ? "bg-surface-600 text-slate-100"
                      : "text-surface-300 hover:text-slate-200 hover:bg-surface-700",
                  )}
                >
                  {group.label}
                  <ChevronDown
                    className={cn(
                      "w-3 h-3 transition-transform duration-150",
                      isExpanded && "rotate-180",
                    )}
                  />
                </button>
                {isExpanded && (
                  <div id={groupMenuId} role="menu" aria-label={group.label} className="ml-3 mt-0.5 border-l border-surface-600 pl-3">
                    {group.items.map(({ href, label }) => {
                      const active =
                        href === `/${format}`
                          ? pathname === `/${format}`
                          : pathname.startsWith(href);
                      return (
                        <Link
                          key={href}
                          href={href}
                          role="menuitem"
                          onClick={onClose}
                          className={cn(
                            "flex items-center px-3 min-h-11 text-sm rounded-md transition-colors",
                            active
                              ? "bg-accent/10 text-accent"
                              : "text-slate-300 hover:bg-surface-600 hover:text-slate-100",
                          )}
                        >
                          {label}
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}

          {/* Guide */}
          <div className="mt-3 pt-3 border-t border-surface-600">
            <Link
              href={`/${format}/guide`}
              onClick={onClose}
              className="flex items-center px-3 min-h-11 text-sm rounded-md text-surface-300 hover:text-slate-200 hover:bg-surface-700 transition-colors"
            >
              Guide
            </Link>
          </div>
        </nav>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Nav (main export)                                                    */
/* ------------------------------------------------------------------ */

export function Nav({ format, formats }: { format: string; formats: FormatInfo[] }) {
  const pathname = usePathname();
  const router = useRouter();
  const [formatOpen, setFormatOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const formatRef = useRef<HTMLDivElement>(null);
  const formatTriggerRef = useRef<HTMLButtonElement>(null);
  const formatMenuRef = useRef<HTMLDivElement>(null);
  const hamburgerRef = useRef<HTMLButtonElement>(null);
  const formatMenuId = "nav-format-menu";

  const currentFormat = formats.find((f) => f.slug === format);
  const displayName = currentFormat?.name || format;

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (formatRef.current && !formatRef.current.contains(e.target as Node)) {
        setFormatOpen(false);
      }
    }
    if (formatOpen) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [formatOpen]);

  const formatKeyDown = useMenuKeyboard(
    formatOpen,
    setFormatOpen,
    formatMenuRef,
    formatTriggerRef,
    '[role="menuitem"]',
  );

  function switchFormat(slug: string) {
    setFormatOpen(false);
    const subpath = pathname.replace(`/${format}`, "");
    router.push(`/${slug}${subpath}`);
  }

  const closeMobile = useCallback(() => {
    setMobileOpen(false);
    // Return focus to hamburger
    requestAnimationFrame(() => hamburgerRef.current?.focus());
  }, []);

  const dashboardLink = { href: `/${format}`, label: "Dashboard" };
  const matchupsLink = { href: `/${format}/matchups`, label: "Matchups" };
  const metaEvLink = { href: `/${format}/meta-ev`, label: "Meta EV" };

  const groups: NavGroup[] = [
    {
      label: "Decks",
      items: [
        { href: `/${format}/optimal-60`, label: "Optimal 60" },
        { href: `/${format}/archetypes`, label: "Archetypes" },
        { href: `/${format}/champions`, label: "Champions League" },
      ],
    },
    {
      label: "Cards",
      items: [
        { href: `/${format}/cards`, label: "Cards" },
        { href: `/${format}/buylist`, label: "Buy List" },
        { href: `/${format}/card-analysis`, label: "Format Edge" },
      ],
    },
    {
      label: "Meta",
      items: [
        { href: `/${format}/tournaments`, label: "Tournaments" },
        { href: `/${format}/players`, label: "Players" },
        { href: `/${format}/trends`, label: "Trends" },
        { href: `/${format}/shifts`, label: "Shifts" },
        { href: `/${format}/forecast`, label: "Forecast" },
      ],
    },
  ];

  const dashboardActive = pathname === `/${format}`;
  const matchupsActive = pathname.startsWith(`/${format}/matchups`);

  return (
    <>
      <nav
        className="border-b border-surface-600 bg-surface-800/80 backdrop-blur-sm sticky top-0 z-50"
        data-testid="main-nav"
        aria-label="Main navigation"
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            <div className="flex items-center gap-3">
              <Link href="/" className="flex items-center gap-2 text-accent font-display font-bold text-lg">
                <Crosshair className="w-5 h-5" />
                Scout
              </Link>

              {/* Format switcher */}
              <div className="relative" ref={formatRef} onKeyDown={formatKeyDown}>
                <button
                  ref={formatTriggerRef}
                  onClick={() => setFormatOpen((prev) => !prev)}
                  aria-expanded={formatOpen}
                  aria-haspopup="menu"
                  aria-controls={formatOpen ? formatMenuId : undefined}
                  className={cn(
                    "flex items-center gap-1.5 text-xs font-mono px-2.5 py-1 rounded-md border transition-colors min-h-11",
                    formatOpen
                      ? "bg-surface-600 border-surface-500 text-slate-100"
                      : "bg-surface-700 border-surface-600 text-surface-300 hover:text-slate-200 hover:border-surface-500",
                  )}
                >
                  {displayName}
                  <ChevronDown
                    className={cn(
                      "w-3 h-3 transition-transform duration-150",
                      formatOpen && "rotate-180",
                    )}
                  />
                </button>

                {formatOpen && (
                  <div
                    ref={formatMenuRef}
                    id={formatMenuId}
                    role="menu"
                    aria-label="Format switcher"
                    className="absolute top-full left-0 mt-1.5 w-80 max-h-[calc(100vh-5rem)] overflow-y-auto bg-surface-700 border border-surface-500 rounded-md shadow-xl shadow-black/40 overflow-hidden z-50"
                  >
                    <FormatMenuGroups
                      formats={formats}
                      current={format}
                      onSelect={switchFormat}
                      itemTabIndex={-1}
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Desktop nav links (hidden on mobile) */}
            <div className="hidden md:flex items-center gap-1">
              <Link
                href={dashboardLink.href}
                className={cn(
                  "px-3 py-1.5 text-sm rounded-md whitespace-nowrap transition-colors min-h-11 flex items-center",
                  dashboardActive
                    ? "bg-surface-600 text-slate-100"
                    : "text-surface-300 hover:text-slate-200 hover:bg-surface-700",
                )}
              >
                Dashboard
              </Link>
              <Link
                href={matchupsLink.href}
                className={cn(
                  "px-3 py-1.5 text-sm rounded-md whitespace-nowrap transition-colors min-h-11 flex items-center",
                  matchupsActive
                    ? "bg-surface-600 text-slate-100"
                    : "text-surface-300 hover:text-slate-200 hover:bg-surface-700",
                )}
              >
                Matchups
              </Link>
              <Link
                href={metaEvLink.href}
                className={cn(
                  "px-3 py-1.5 text-sm rounded-md whitespace-nowrap transition-colors min-h-11 flex items-center",
                  pathname.startsWith(`/${format}/meta-ev`)
                    ? "bg-surface-600 text-slate-100"
                    : "text-surface-300 hover:text-slate-200 hover:bg-surface-700",
                )}
              >
                Meta EV
              </Link>
              {groups.map((group) => (
                <NavDropdown
                  key={group.label}
                  group={group}
                  pathname={pathname}
                  format={format}
                />
              ))}
              <Link
                href={`/${format}/guide`}
                className="px-3 py-1.5 text-sm rounded-md whitespace-nowrap transition-colors ml-1 border-l border-surface-600 pl-3 text-surface-300 hover:text-slate-200 hover:bg-surface-700 min-h-11 flex items-center"
              >
                Guide
              </Link>
            </div>

            {/* Hamburger button (visible on mobile only) */}
            <button
              ref={hamburgerRef}
              onClick={() => setMobileOpen(true)}
              aria-label="Open menu"
              aria-expanded={mobileOpen}
              aria-controls="mobile-nav-drawer"
              className="md:hidden flex items-center justify-center min-h-11 min-w-11 rounded-md text-surface-300 hover:text-slate-100 hover:bg-surface-700 transition-colors"
            >
              <Menu className="w-5 h-5" />
            </button>
          </div>
        </div>
      </nav>

      {/* Mobile drawer */}
      <MobileDrawer
        open={mobileOpen}
        onClose={closeMobile}
        format={format}
        formats={formats}
        pathname={pathname}
        groups={groups}
        dashboardHref={dashboardLink.href}
        dashboardActive={dashboardActive}
        matchupsHref={matchupsLink.href}
        matchupsActive={matchupsActive}
        onSwitchFormat={switchFormat}
      />
    </>
  );
}
