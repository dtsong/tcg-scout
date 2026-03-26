"use client";

import { useState, useEffect } from "react";
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

export function SidebarNavClient({ format, formats }: SidebarNavClientProps) {
  const pathname = usePathname();
  const isDashboard = pathname === `/${format}`;
  const [activeSection, setActiveSection] = useState<string | null>(null);

  useEffect(() => {
    if (!isDashboard) {
      setActiveSection(null);
      return;
    }

    const sectionIds = dashboardSections.map((s) => s.id);
    const elements = sectionIds
      .map((id) => document.getElementById(id))
      .filter(Boolean) as HTMLElement[];

    if (elements.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        // Find the topmost visible section
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible.length > 0) {
          setActiveSection(visible[0].target.id);
        } else if (entries.every((e) => !e.isIntersecting)) {
          setActiveSection(null);
        }
      },
      { rootMargin: "-20% 0px -60% 0px", threshold: 0 },
    );

    elements.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [isDashboard, format]);

  const isQuickLinkActive = (anchor: string) => {
    const href = `/${format}/${anchor}`;
    return pathname === href || pathname.startsWith(`${href}/`);
  };

  return (
    <>
      {/* Dashboard Sections - only on dashboard */}
      {isDashboard && (
        <div>
          <h3 className="font-display text-xs font-semibold text-surface-300 uppercase tracking-wider mb-3">
            Dashboard
          </h3>
          <nav className="space-y-1">
            {dashboardSections.map(({ id, label }) => (
              <a
                key={id}
                href={`#${id}`}
                className={`block py-1 pl-3 border-l-2 transition-colors ${
                  activeSection === id
                    ? "border-l-accent text-slate-200"
                    : "border-transparent text-surface-400 hover:text-slate-200 hover:border-l-accent"
                }`}
              >
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
            <Link
              key={anchor}
              href={`/${format}/${anchor}`}
              className={`block py-1 pl-3 border-l-2 transition-colors ${
                isQuickLinkActive(anchor)
                  ? "border-l-accent text-slate-200"
                  : "border-transparent text-surface-400 hover:text-slate-200 hover:border-l-accent"
              }`}
            >
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
              <Link
                key={f.slug}
                href={`/${f.slug}`}
                className={`block py-1 pl-3 border-l-2 transition-colors ${
                  f.slug === format
                    ? "border-l-accent text-slate-200"
                    : "border-transparent text-surface-400 hover:text-slate-200 hover:border-l-accent"
                }`}
              >
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
