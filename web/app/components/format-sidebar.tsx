import Link from "next/link";
import type { MetaData, FormatInfo } from "@/app/lib/types";

interface FormatSidebarProps {
  meta: MetaData;
  format: string;
  formats: FormatInfo[];
  rotationDays?: number;
}

const quickLinks = [
  { anchor: "optimal-60", label: "Optimal 60" },
  { anchor: "archetypes", label: "Archetypes" },
  { anchor: "matchups", label: "Matchups" },
  { anchor: "card-analysis", label: "Format Edge" },
  { anchor: "buylist", label: "Buy List" },
  { anchor: "trends", label: "Trends" },
  { anchor: "champions", label: "Champions League" },
];

export function FormatSidebar({ meta, format, formats, rotationDays }: FormatSidebarProps) {
  return (
    <div className="space-y-6 text-sm">
      {/* Format Stats */}
      <div>
        <h3 className="font-display text-xs font-semibold text-surface-300 uppercase tracking-wider mb-3">
          Format Stats
        </h3>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-surface-400">Tournaments</span>
            <span className="font-mono text-slate-200 tabular-nums">{meta.tournament_count.toLocaleString()}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-surface-400">Decks</span>
            <span className="font-mono text-slate-200 tabular-nums">{meta.deck_count.toLocaleString()}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-surface-400">Range</span>
            <span className="font-mono text-xs text-slate-200 tabular-nums">{meta.date_range?.start?.slice(5) ?? "?"} - {meta.date_range?.end?.slice(5) ?? "?"}</span>
          </div>
          {rotationDays !== undefined && rotationDays > 0 && (
            <div className="flex items-center justify-between">
              <span className="text-surface-400">Set Legal</span>
              <span className="font-mono text-accent tabular-nums">{rotationDays}d</span>
            </div>
          )}
        </div>
      </div>

      {/* Dashboard Sections */}
      <div>
        <h3 className="font-display text-xs font-semibold text-surface-300 uppercase tracking-wider mb-3">
          On This Page
        </h3>
        <nav className="space-y-1">
          {[
            { id: "hero", label: "Top Decks" },
            { id: "breakout", label: "Breakout Watch" },
            { id: "tier-list", label: "Tier List" },
          ].map(({ id, label }) => (
            <a
              key={id}
              href={`#${id}`}
              className="block py-1 pl-3 border-l-2 border-transparent text-surface-400 hover:text-slate-200 hover:border-l-accent transition-colors"
            >
              {label}
            </a>
          ))}
        </nav>
      </div>

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
              className="block py-1 pl-3 border-l-2 border-transparent text-surface-400 hover:text-slate-200 hover:border-l-accent transition-colors"
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
    </div>
  );
}
