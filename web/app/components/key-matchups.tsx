"use client";

import Link from "next/link";
import type { MatchupMatrixData } from "@/app/lib/types";
import { cn } from "@/app/lib/utils";

interface MatchupEntry {
  archetype: string;
  value: number;
  sampleSize: number;
}

function isWinRate(source?: string): boolean {
  return source === "labs-h2h" || source === "labs-records";
}

function formatValue(value: number, source?: string): string {
  if (isWinRate(source)) {
    return `${Math.round(value * 100)}%`;
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}`;
}

function barWidth(value: number, source?: string): number {
  if (isWinRate(source)) {
    // Scale: 50% = 0 width, 100% or 0% = full width
    return Math.min(100, Math.abs(value - 0.5) * 200);
  }
  // Co-occurrence: scale by absolute value, max at +-5
  return Math.min(100, (Math.abs(value) / 5) * 100);
}

export function KeyMatchups({
  data,
  archetype,
  format,
}: {
  data: MatchupMatrixData;
  archetype: string;
  format: string;
}) {
  const idx = data.archetypes.indexOf(archetype);
  if (idx === -1) return null;

  const winRate = isWinRate(data.source);

  // Extract this archetype's matchup row
  const entries: MatchupEntry[] = [];
  for (let j = 0; j < data.archetypes.length; j++) {
    if (j === idx) continue;
    const value = data.matrix[idx]?.[j];
    if (value === null || value === undefined) continue;
    const sampleSize = data.sample_sizes[idx]?.[j] ?? 0;
    // Filter out insufficient data
    if (winRate && sampleSize < 5) continue;
    if (!winRate && sampleSize < 10) continue;
    entries.push({
      archetype: data.archetypes[j],
      value,
      sampleSize,
    });
  }

  if (entries.length === 0) return null;

  // Sort for favorable (high value) and unfavorable (low value)
  const sorted = [...entries].sort((a, b) => b.value - a.value);
  const favorable = sorted.slice(0, 3).filter((e) =>
    winRate ? e.value > 0.5 : e.value > 0,
  );
  const unfavorable = sorted
    .slice(-3)
    .reverse()
    .filter((e) => (winRate ? e.value < 0.5 : e.value < 0));

  if (favorable.length === 0 && unfavorable.length === 0) return null;

  return (
    <section>
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="font-display text-lg font-semibold text-slate-100">
          Key Matchups
        </h2>
        <Link
          href={`/${format}/matchups`}
          className="text-xs text-accent hover:text-accent/80 transition-colors"
        >
          View full matchup data &rarr;
        </Link>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        {favorable.length > 0 && (
          <div>
            <h3 className="text-xs font-medium text-emerald-400 uppercase tracking-wider mb-3">
              Favorable
            </h3>
            <div className="space-y-2">
              {favorable.map((entry) => (
                <MatchupRow
                  key={entry.archetype}
                  entry={entry}
                  color="emerald"
                  source={data.source}
                />
              ))}
            </div>
          </div>
        )}
        {unfavorable.length > 0 && (
          <div>
            <h3 className="text-xs font-medium text-red-400 uppercase tracking-wider mb-3">
              Unfavorable
            </h3>
            <div className="space-y-2">
              {unfavorable.map((entry) => (
                <MatchupRow
                  key={entry.archetype}
                  entry={entry}
                  color="red"
                  source={data.source}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {data.source && (
        <p className="text-[10px] text-surface-500 mt-3">
          {winRate
            ? "Win rates based on tournament records."
            : "Based on average placement advantage when both archetypes appear in the same tournament."}
          {" "}
          {entries.some((e) => e.sampleSize < 20) && (
            <span className="text-amber-500/70">Some matchups have limited data.</span>
          )}
        </p>
      )}
    </section>
  );
}

function MatchupRow({
  entry,
  color,
  source,
}: {
  entry: MatchupEntry;
  color: "emerald" | "red";
  source?: string;
}) {
  const lowSample = entry.sampleSize < 20;

  return (
    <div className={cn("flex items-center gap-3 py-1.5", lowSample && "opacity-70")}>
      <span
        className={cn(
          "text-sm font-mono tabular-nums w-12 text-right font-medium",
          color === "emerald" ? "text-emerald-300" : "text-red-300",
        )}
      >
        {formatValue(entry.value, source)}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm text-surface-200 truncate">
            {entry.archetype}
          </span>
          {lowSample && (
            <span className="text-[9px] text-amber-500/70 shrink-0">
              Limited data
            </span>
          )}
        </div>
        {/* Bar */}
        <div className="h-1 bg-surface-700 rounded-full mt-1">
          <div
            className={cn(
              "h-1 rounded-full",
              color === "emerald" ? "bg-emerald-500/50" : "bg-red-500/50",
            )}
            style={{ width: `${barWidth(entry.value, source)}%` }}
          />
        </div>
      </div>
      <span className="text-[10px] text-surface-500 tabular-nums shrink-0">
        n={entry.sampleSize}
      </span>
    </div>
  );
}
