"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { FormatInfo } from "@/app/lib/types";

interface SidebarNavClientProps {
  format: string;
  formats: FormatInfo[];
}

const dashboardSections = [
  { id: "hero", label: "Top Decks" },
  { id: "breakout", label: "Breakout Watch" },
  { id: "tier-list", label: "Tier List" },
];

const quickLinks = [
  { anchor: "optimal-60", label: "Optimal 60" },
  { anchor: "archetypes", label: "Archetypes" },
  { anchor: "matchups", label: "Matchups" },
  { anchor: "card-analysis", label: "Format Edge" },
  { anchor: "buylist", label: "Buy List" },
  { anchor: "trends", label: "Trends" },
  { anchor: "champions", label: "Champions League" },
];

function navLinkClass(isActive: boolean): string {
  return `block py-1 pl-3 border-l-2 transition-colors ${
    isActive
      ? "border-l-accent text-slate-200"
      : "border-transparent text-surface-400 hover:text-slate-200 hover:border-l-accent"
  }`;
}

export function SidebarNavClient({ format, formats }: SidebarNavClientProps) {
  const pathname = usePathname();
  const isDashboard = pathname === `/${format}`;
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const visibleRef = useRef(new Set<string>());

  useEffect(() => {
    if (!isDashboard) {
      setActiveSection(null);
      visibleRef.current.clear();
      return;
    }

    const elements = dashboardSections
      .map((s) => document.getElementById(s.id))
      .filter(Boolean) as HTMLElement[];

    if (process.env.NODE_ENV === "development" && elements.length > 0 && elements.length < dashboardSections.length) {
      const missing = dashboardSections.filter((s) => !document.getElementById(s.id)).map((s) => s.id);
      console.warn(`[SidebarNav] Dashboard sections not found in DOM: ${missing.join(", ")}`);
    }

    if (elements.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            visibleRef.current.add(entry.target.id);
          } else {
            visibleRef.current.delete(entry.target.id);
          }
        }

        if (visibleRef.current.size > 0) {
          // Pick the topmost visible section by DOM order
          const topmost = dashboardSections.find((s) => visibleRef.current.has(s.id));
          setActiveSection(topmost?.id ?? null);
        } else {
          setActiveSection(null);
        }
      },
      { rootMargin: "-20% 0px -60% 0px", threshold: 0 },
    );

    elements.forEach((el) => observer.observe(el));
    return () => {
      observer.disconnect();
      visibleRef.current.clear();
    };
  }, [isDashboard, format]);

  function isQuickLinkActive(anchor: string): boolean {
    const href = `/${format}/${anchor}`;
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  return (
    <>
      {/* Dashboard Sections */}
      {isDashboard && (
        <div>
          <h3 className="font-display text-xs font-semibold text-surface-300 uppercase tracking-wider mb-3">
            Dashboard
          </h3>
          <nav className="space-y-1">
            {dashboardSections.map(({ id, label }) => (
              <a key={id} href={`#${id}`} className={navLinkClass(activeSection === id)}>
                {label}
              </a>
            ))}
          </nav>
        </div>
      )}

      {/* Quick Links */}
      <div>
        <h3 className="font-display text-xs font-semibold text-surface-300 uppercase tracking-wider mb-3">
          Quick Links
        </h3>
        <nav className="space-y-1">
          {quickLinks.map(({ anchor, label }) => (
            <Link key={anchor} href={`/${format}/${anchor}`} className={navLinkClass(isQuickLinkActive(anchor))}>
              {label}
            </Link>
          ))}
        </nav>
      </div>

      {/* Format Switcher */}
      {formats.length > 1 && (
        <div>
          <h3 className="font-display text-xs font-semibold text-surface-300 uppercase tracking-wider mb-3">
            Formats
          </h3>
          <nav className="space-y-1">
            {formats.map((f) => (
              <Link key={f.slug} href={`/${f.slug}`} className={navLinkClass(f.slug === format)}>
                {f.name_en}
                {f.status === "frozen" && (
                  <span className="ml-1 text-[10px] text-surface-500">archived</span>
                )}
              </Link>
            ))}
          </nav>
        </div>
      )}
    </>
  );
}
