"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { ArrowLeft, TrendingUp, TrendingDown, Zap } from "lucide-react";
import type { MetaEvolutionMovement } from "@/app/lib/types";

type DirectionFilter = "all" | "adopted" | "dropped";
type SortMode = "magnitude" | "recency";

interface ShiftsClientProps {
  format: string;
  movements: MetaEvolutionMovement[];
}

export function ShiftsClient({ format, movements }: ShiftsClientProps) {
  const [directionFilter, setDirectionFilter] = useState<DirectionFilter>("all");
  const [archetypeFilter, setArchetypeFilter] = useState<string>("all");
  const [sortMode, setSortMode] = useState<SortMode>("magnitude");

  const archetypes = useMemo(() => {
    const unique = [...new Set(movements.map((m) => m.archetype))];
    return unique.sort();
  }, [movements]);

  const maxDelta = useMemo(
    () => Math.max(...movements.map((m) => m.delta), 1),
    [movements]
  );

  const latestWeek = useMemo(() => {
    if (movements.length === 0) return null;
    return movements[0].week;
  }, [movements]);

  const filtered = useMemo(() => {
    let result = movements;

    if (directionFilter !== "all") {
      result = result.filter((m) => m.direction === directionFilter);
    }

    if (archetypeFilter !== "all") {
      result = result.filter((m) => m.archetype === archetypeFilter);
    }

    if (sortMode === "magnitude") {
      result = [...result].sort((a, b) => b.delta - a.delta);
    }
    // recency is the default sort from backend (week DESC, delta DESC)

    return result;
  }, [movements, directionFilter, archetypeFilter, sortMode]);

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
        {/* Direction filter */}
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

        {/* Archetype filter */}
        <select
          value={archetypeFilter}
          onChange={(e) => setArchetypeFilter(e.target.value)}
          className="bg-surface-800 border border-surface-600 text-sm text-slate-300 rounded-lg px-3 py-1.5 focus:outline-none focus:border-surface-400"
        >
          <option value="all">All archetypes</option>
          {archetypes.map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>

        {/* Sort toggle */}
        <div className="inline-flex rounded-lg border border-surface-600 overflow-hidden">
          {(["magnitude", "recency"] as SortMode[]).map((mode) => (
            <button
              key={mode}
              onClick={() => setSortMode(mode)}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                sortMode === mode
                  ? "bg-surface-600 text-slate-100"
                  : "bg-surface-800 text-surface-300 hover:text-slate-200 hover:bg-surface-700"
              }`}
            >
              {mode === "magnitude" ? "By magnitude" : "By recency"}
            </button>
          ))}
        </div>

        <span className="text-xs text-surface-400 ml-auto">
          {filtered.length} shift{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Results */}
      <div className="space-y-2">
        {filtered.map((m, i) => {
          const barWidth = (m.delta / maxDelta) * 100;
          const isHigh = m.delta >= 30;
          const isMedium = m.delta >= 10 && m.delta < 30;

          return (
            <div
              key={`${m.card}-${m.archetype}-${m.week}-${i}`}
              className="relative bg-surface-800 border border-surface-600 rounded-lg p-4 overflow-hidden"
            >
              {/* Magnitude bar background */}
              <div
                className={`absolute inset-y-0 left-0 ${
                  m.direction === "adopted" ? "bg-emerald-500/8" : "bg-red-500/8"
                }`}
                style={{ width: `${barWidth}%` }}
              />

              <div className="relative flex items-center justify-between gap-4">
                {/* Left side: icon + card info */}
                <div className="flex items-center gap-3 min-w-0">
                  {m.direction === "adopted" ? (
                    <TrendingUp
                      className={`w-4 h-4 shrink-0 ${
                        isHigh ? "text-emerald-400" : isMedium ? "text-emerald-400/70" : "text-surface-400"
                      }`}
                    />
                  ) : (
                    <TrendingDown
                      className={`w-4 h-4 shrink-0 ${
                        isHigh ? "text-red-400" : isMedium ? "text-red-400/70" : "text-surface-400"
                      }`}
                    />
                  )}
                  <div className="min-w-0">
                    <span
                      className={`text-sm truncate block ${
                        isHigh ? "font-semibold text-slate-100" : isMedium ? "text-slate-200" : "text-surface-300"
                      }`}
                    >
                      {m.card}
                    </span>
                    <span className="text-[11px] text-surface-400 flex items-center gap-1.5">
                      in{" "}
                      {m.archetype_slug ? (
                        <Link
                          href={`/${format}/archetypes/${m.archetype_slug}`}
                          className="text-surface-300 hover:text-slate-200 underline decoration-surface-600 underline-offset-2"
                        >
                          {m.archetype}
                        </Link>
                      ) : (
                        m.archetype
                      )}
                      {m.deck_count != null && (
                        <span className="text-surface-400">({m.deck_count} decks)</span>
                      )}
                    </span>
                  </div>
                </div>

                {/* Right side: percentages */}
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
                    {m.direction === "adopted" ? "+" : "-"}{m.delta.toFixed(0)}pp
                  </span>
                </div>
              </div>

              {/* Week label for non-latest weeks */}
              {m.week !== latestWeek && (
                <span className="absolute top-1.5 right-2 text-[10px] text-surface-400">
                  {formatWeek(m.week)}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-12">
          <p className="text-surface-300 text-sm">No shifts match the current filters.</p>
        </div>
      )}
    </div>
  );
}
