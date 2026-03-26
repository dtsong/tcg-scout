import type { MetaData, FormatInfo } from "@/app/lib/types";
import { SidebarNavClient } from "./sidebar-nav-client";

interface FormatSidebarProps {
  meta: MetaData;
  format: string;
  formats: FormatInfo[];
  rotationDays?: number;
}

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

      <SidebarNavClient format={format} formats={formats} />
    </div>
  );
}
