"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { ArrowLeft, TrendingUp, TrendingDown, Zap, ChevronDown, ChevronRight } from "lucide-react";
import type { MetaEvolutionMovement } from "@/app/lib/types";

type DirectionFilter = "all" | "adopted" | "dropped";

interface ArchetypeGroup {
  archetype: string;
  archetype_slug?: string;
  deck_count?: number;
  adopted: MetaEvolutionMovement[];
  dropped: MetaEvolutionMovement[];
  maxDelta: number;
  week: string;
}

interface ShiftsClientProps {
  format: string;
  movements: MetaEvolutionMovement[];
}

export function ShiftsClient({ format, movements }: ShiftsClientProps) {
  const [directionFilter, setDirectionFilter] = useState<DirectionFilter>("all");
  const [expandedArchetypes, setExpandedArchetypes] = useState<Set<string>>(new Set());

  const latestWeek = useMemo(() => {
    if (movements.length === 0) return null;
    return movements.reduce((latest, m) => (m.week > latest ? m.week : latest), movements[0].week);
  }, [movements]);

  const groups = useMemo(() => {
    const byArchetype = new Map<string, MetaEvolutionMovement[]>();
    for (const m of movements) {
      const list = byArchetype.get(m.archetype) || [];
      list.push(m);
      byArchetype.set(m.archetype, list);
    }

    const result: ArchetypeGroup[] = [];
    for (const [archetype, items] of byArchetype) {
      const adopted = items
        .filter((m) => m.direction === "adopted")
        .sort((a, b) => b.delta - a.delta);
      const dropped = items
        .filter((m) => m.direction === "dropped")
        .sort((a, b) => b.delta - a.delta);

      if (
        (directionFilter === "adopted" && adopted.length === 0) ||
        (directionFilter === "dropped" && dropped.length === 0)
      ) {
        continue;
      }

      result.push({
        archetype,
        archetype_slug: items[0].archetype_slug,
        deck_count: items[0].deck_count,
        adopted,
        dropped,
        maxDelta: Math.max(...items.map((m) => m.delta), 1),
        week: items.reduce((latest, m) => (m.week > latest ? m.week : latest), items[0].week),
      });
    }

    return result.sort((a, b) => b.maxDelta - a.maxDelta);
  }, [movements, directionFilter]);

  const totalShifts = useMemo(() => {
    return groups.reduce((sum, g) => {
      if (directionFilter === "adopted") return sum + g.adopted.length;
      if (directionFilter === "dropped") return sum + g.dropped.length;
      return sum + g.adopted.length + g.dropped.length;
    }, 0);
  }, [groups, directionFilter]);

  const toggleArchetype = (archetype: string) => {
    setExpandedArchetypes((prev) => {
      const next = new Set(prev);
      if (next.has(archetype)) next.delete(archetype);
      else next.add(archetype);
      return next;
    });
  };

  const expandAll = () => setExpandedArchetypes(new Set(groups.map((g) => g.archetype)));
  const collapseAll = () => setExpandedArchetypes(new Set());

  const formatWeek = (iso: string) => {
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  };

  if (movements.length === 0) {
    return (
      <div className="text-center py-24">
        <Zap className="w-8 h-8 text-surface-400 mx-auto mb-4" />
        <p className="text-surface-300">No significant copy-count shifts detected yet.</p>
        <Link href={`/${format}`} className="mt-4 inline-block text-sm text-amber-400 hover:text-amber-300">
          Back to dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link
          href={`/${format}`}
          className="inline-flex items-center gap-1 text-xs text-surface-300 hover:text-slate-200 mb-3"
        >
          <ArrowLeft className="w-3 h-3" />
          Dashboard
        </Link>
        <div className="flex items-center justify-between">
          <h1 className="font-display text-2xl font-bold text-slate-100 flex items-center gap-3">
            <Zap className="w-6 h-6 text-amber-400" />
            Copy-Count Shifts
          </h1>
          {latestWeek && (
            <span className="text-xs text-surface-300">
              Latest: week of {formatWeek(latestWeek)}
            </span>
          )}
        </div>
        <p className="text-sm text-surface-300 mt-1">
          Cards crossing adoption or drop thresholds across top-tier archetypes
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="inline-flex rounded-lg border border-surface-600 overflow-hidden">
          {(["all", "adopted", "dropped"] as DirectionFilter[]).map((dir) => (
            <button
              key={dir}
              onClick={() => setDirectionFilter(dir)}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                directionFilter === dir
                  ? "bg-surface-600 text-slate-100"
                  : "bg-surface-800 text-surface-300 hover:text-slate-200 hover:bg-surface-700"
              }`}
            >
              {dir === "all" ? "All" : dir === "adopted" ? "Rises" : "Drops"}
            </button>
          ))}
        </div>

        <div className="flex gap-2 text-[11px]">
          <button onClick={expandAll} className="text-surface-400 hover:text-slate-200">
            Expand all
          </button>
          <span className="text-surface-600">|</span>
          <button onClick={collapseAll} className="text-surface-400 hover:text-slate-200">
            Collapse all
          </button>
        </div>

        <span className="text-xs text-surface-400 ml-auto">
          {totalShifts} shift{totalShifts !== 1 ? "s" : ""} across {groups.length} archetype{groups.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Grouped results */}
      <div className="space-y-3">
        {groups.map((group) => {
          const isExpanded = expandedArchetypes.has(group.archetype);
          const adopted = directionFilter === "dropped" ? [] : group.adopted;
          const dropped = directionFilter === "adopted" ? [] : group.dropped;
          const shiftCount = adopted.length + dropped.length;

          return (
            <div
              key={group.archetype}
              className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden"
            >
              {/* Archetype header */}
              <button
                onClick={() => toggleArchetype(group.archetype)}
                className="w-full flex items-center justify-between gap-3 px-4 py-3 hover:bg-surface-700/50 transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0">
                  {isExpanded ? (
                    <ChevronDown className="w-4 h-4 text-surface-400 shrink-0" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-surface-400 shrink-0" />
                  )}
                  <span className="text-sm font-medium text-slate-100 truncate">
                    {group.archetype}
                  </span>
                  {group.deck_count != null && (
                    <span className="text-[11px] text-surface-400">
                      {group.deck_count} decks
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {adopted.length > 0 && (
                    <span className="flex items-center gap-1 text-[11px] text-emerald-400/70">
                      <TrendingUp className="w-3 h-3" />
                      {adopted.length}
                    </span>
                  )}
                  {dropped.length > 0 && (
                    <span className="flex items-center gap-1 text-[11px] text-red-400/70">
                      <TrendingDown className="w-3 h-3" />
                      {dropped.length}
                    </span>
                  )}
                  <span className="text-[11px] text-surface-400">
                    {shiftCount} shift{shiftCount !== 1 ? "s" : ""}
                  </span>
                </div>
              </button>

              {/* Expanded card list */}
              {isExpanded && (
                <div className="border-t border-surface-700 divide-y divide-surface-700/50">
                  {adopted.map((m, i) => (
                    <ShiftRow key={`a-${i}`} m={m} maxDelta={group.maxDelta} />
                  ))}
                  {dropped.map((m, i) => (
                    <ShiftRow key={`d-${i}`} m={m} maxDelta={group.maxDelta} />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {groups.length === 0 && (
        <div className="text-center py-12">
          <p className="text-surface-300 text-sm">No shifts match the current filters.</p>
        </div>
      )}
    </div>
  );
}

function ShiftRow({ m, maxDelta }: { m: MetaEvolutionMovement; maxDelta: number }) {
  const barWidth = (m.delta / maxDelta) * 100;
  const isHigh = m.delta >= 30;
  const isMedium = m.delta >= 10 && m.delta < 30;

  return (
    <div className="relative px-4 py-2.5 overflow-hidden">
      <div
        className={`absolute inset-y-0 left-0 ${
          m.direction === "adopted" ? "bg-emerald-500/8" : "bg-red-500/8"
        }`}
        style={{ width: `${barWidth}%` }}
      />
      <div className="relative flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          {m.direction === "adopted" ? (
            <TrendingUp
              className={`w-3.5 h-3.5 shrink-0 ${
                isHigh ? "text-emerald-400" : isMedium ? "text-emerald-400/70" : "text-surface-400"
              }`}
            />
          ) : (
            <TrendingDown
              className={`w-3.5 h-3.5 shrink-0 ${
                isHigh ? "text-red-400" : isMedium ? "text-red-400/70" : "text-surface-400"
              }`}
            />
          )}
          <span
            className={`text-sm truncate ${
              isHigh ? "font-medium text-slate-100" : isMedium ? "text-slate-200" : "text-surface-300"
            }`}
          >
            {m.card}
          </span>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <span
            className={`font-mono text-xs whitespace-nowrap ${
              isHigh ? "text-slate-200" : "text-surface-300"
            }`}
          >
            {m.from_pct.toFixed(0)}% &rarr; {m.to_pct.toFixed(0)}%
          </span>
          <span
            className={`font-mono text-xs font-medium px-1.5 py-0.5 rounded ${
              m.direction === "adopted"
                ? isHigh
                  ? "text-emerald-400 bg-emerald-500/15"
                  : "text-emerald-400/70 bg-emerald-500/8"
                : isHigh
                  ? "text-red-400 bg-red-500/15"
                  : "text-red-400/70 bg-red-500/8"
            }`}
          >
            {m.direction === "adopted" ? "+" : "-"}{m.delta.toFixed(0)}%
          </span>
        </div>
      </div>
    </div>
  );
}
