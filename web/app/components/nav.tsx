"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/app/lib/utils";
import { Crosshair, ChevronDown } from "lucide-react";
import type { FormatInfo } from "@/app/lib/types";

interface NavGroup {
  label: string;
  items: { href: string; label: string }[];
}

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

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((prev) => !prev)}
        className={cn(
          "flex items-center gap-1 px-3 py-1.5 text-sm rounded-md whitespace-nowrap transition-colors",
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
        <div className="absolute top-full left-0 mt-1.5 min-w-[180px] bg-surface-700 border border-surface-500 rounded-lg shadow-xl shadow-black/40 overflow-hidden z-50">
          {group.items.map(({ href, label }) => {
            const active =
              href === `/${format}`
                ? pathname === `/${format}`
                : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                className={cn(
                  "block px-3 py-2 text-sm transition-colors",
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

export function Nav({ format, formats }: { format: string; formats: FormatInfo[] }) {
  const pathname = usePathname();
  const router = useRouter();
  const [formatOpen, setFormatOpen] = useState(false);
  const formatRef = useRef<HTMLDivElement>(null);

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

  function switchFormat(slug: string) {
    setFormatOpen(false);
    const subpath = pathname.replace(`/${format}`, "");
    router.push(`/${slug}${subpath}`);
  }

  const dashboardLink = { href: `/${format}`, label: "Dashboard" };

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
        { href: `/${format}/trends`, label: "Trends" },
        { href: `/${format}/shifts`, label: "Shifts" },
        { href: `/${format}/forecast`, label: "Forecast" },
      ],
    },
  ];

  const dashboardActive = pathname === `/${format}`;

  return (
    <nav className="border-b border-surface-600 bg-surface-800/80 backdrop-blur-sm sticky top-0 z-50" data-testid="main-nav">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2 text-accent font-display font-bold text-lg">
              <Crosshair className="w-5 h-5" />
              Scout
            </Link>

            {/* Format switcher */}
            <div className="relative" ref={formatRef}>
              <button
                onClick={() => setFormatOpen((prev) => !prev)}
                className={cn(
                  "flex items-center gap-1.5 text-xs font-mono px-2.5 py-1 rounded-md border transition-colors",
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
                <div className="absolute top-full left-0 mt-1.5 min-w-[200px] bg-surface-700 border border-surface-500 rounded-lg shadow-xl shadow-black/40 overflow-hidden z-50">
                  {formats.map((f) => (
                    <button
                      key={f.slug}
                      onClick={() => switchFormat(f.slug)}
                      className={cn(
                        "w-full text-left px-3 py-2.5 transition-colors",
                        f.slug === format
                          ? "bg-accent/10 text-accent"
                          : "text-slate-300 hover:bg-surface-600 hover:text-slate-100",
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="text-sm font-medium">{f.name}</span>
                          <span className="text-xs text-surface-400 ml-2">{f.name_en}</span>
                        </div>
                        {f.status === "upcoming" && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-600 text-surface-400">
                            Soon
                          </span>
                        )}
                      </div>
                      {f.tournament_count != null && f.tournament_count > 0 && (
                        <div className="text-[11px] text-surface-400 font-mono mt-0.5">
                          {f.tournament_count} tournaments / {f.deck_count} decks
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Link
              href={dashboardLink.href}
              className={cn(
                "px-3 py-1.5 text-sm rounded-md whitespace-nowrap transition-colors",
                dashboardActive
                  ? "bg-surface-600 text-slate-100"
                  : "text-surface-300 hover:text-slate-200 hover:bg-surface-700",
              )}
            >
              Dashboard
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
              className="px-3 py-1.5 text-sm rounded-md whitespace-nowrap transition-colors ml-1 border-l border-surface-600 pl-3 text-surface-300 hover:text-slate-200 hover:bg-surface-700"
            >
              Guide
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
}
