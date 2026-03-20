"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/app/lib/utils";
import { Crosshair, ChevronDown } from "lucide-react";
import type { FormatInfo } from "@/app/lib/types";

export function Nav({ format, formats }: { format: string; formats: FormatInfo[] }) {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentFormat = formats.find((f) => f.slug === format);
  const displayName = currentFormat?.name || format;

  // Close dropdown on click outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  function switchFormat(slug: string) {
    setOpen(false);
    // Preserve the current sub-page (e.g. /archetypes, /trends)
    const subpath = pathname.replace(`/${format}`, "");
    router.push(`/${slug}${subpath}`);
  }

  const links = [
    { href: `/${format}`, label: "Dashboard" },
    { href: `/${format}/archetypes`, label: "Archetypes" },
    { href: `/${format}/cards`, label: "Cards" },
    { href: `/${format}/card-analysis`, label: "Format Edge" },
    { href: `/${format}/buylist`, label: "Buy List" },
    { href: `/${format}/trends`, label: "Trends" },
    { href: `/${format}/champions`, label: "Champions League" },
  ];

  return (
    <nav className="border-b border-surface-600 bg-surface-800/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2 text-accent font-display font-bold text-lg">
              <Crosshair className="w-5 h-5" />
              Scout
            </Link>

            {/* Format switcher */}
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setOpen((prev) => !prev)}
                className={cn(
                  "flex items-center gap-1.5 text-xs font-mono px-2.5 py-1 rounded-md border transition-colors",
                  open
                    ? "bg-surface-600 border-surface-500 text-slate-100"
                    : "bg-surface-700 border-surface-600 text-surface-300 hover:text-slate-200 hover:border-surface-500",
                )}
              >
                {displayName}
                <ChevronDown
                  className={cn(
                    "w-3 h-3 transition-transform duration-150",
                    open && "rotate-180",
                  )}
                />
              </button>

              {open && (
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
          <div className="flex items-center gap-1 overflow-x-auto">
            {links.map(({ href, label }) => {
              const active =
                href === `/${format}`
                  ? pathname === `/${format}`
                  : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "px-3 py-1.5 text-sm rounded-md whitespace-nowrap transition-colors",
                    active
                      ? "bg-surface-600 text-slate-100"
                      : "text-surface-300 hover:text-slate-200 hover:bg-surface-700",
                  )}
                >
                  {label}
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </nav>
  );
}
