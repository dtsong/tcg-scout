"use client";

import type { MatchupMatrixData } from "@/app/lib/types";
import { MatchupHeatMatrix } from "@/app/components/matchup-heat-matrix";
import { Tooltip } from "@/app/components/tooltip";

function sourceLabel(source?: string): string {
  switch (source) {
    case "labs-h2h":
      return "Head-to-head match results";
    case "labs-records":
      return "Win-loss-tie tournament records";
    case "co-occurrence":
      return "Placement performance advantage";
    default:
      return "Matchup data";
  }
}

function sourceDescription(source?: string): string {
  switch (source) {
    case "labs-h2h":
      return "Based on actual game-by-game results from international tournaments. Win rates reflect real head-to-head outcomes with statistical confidence intervals.";
    case "labs-records":
      return "Derived from tournament win-loss records. Compares archetype performance within the same events. More reliable than placement-based data but not true head-to-head results.";
    case "co-occurrence":
      return "Compares average tournament placements when two archetypes appear in the same event. A positive value means the row archetype tends to finish higher. This is a performance proxy, not a direct matchup win rate.";
    default:
      return "Matchup analysis data.";
  }
}

function methodologyLabel(data: MatchupMatrixData): string {
  if (data.methodology) return data.methodology;
  if (data.source === "labs-h2h") return "Win Rate";
  if (data.source === "labs-records") return "Win Rate (estimated)";
  return "Performance Advantage";
}

export function MatchupsClient({
  data,
  format,
  tournamentCount,
}: {
  data: MatchupMatrixData | null;
  format: string;
  tournamentCount: number;
}) {
  if (!data || data.archetypes.length === 0) {
    return (
      <div className="text-center py-24">
        <h1 className="text-2xl font-semibold text-slate-100 mb-4">
          Matchup Matrix
        </h1>
        <p className="text-surface-300">
          Not enough data to compute matchups yet. Check back after more
          tournaments are recorded.
        </p>
      </div>
    );
  }

  const isWinRate = data.source === "labs-h2h" || data.source === "labs-records";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-slate-100">
          Matchup Matrix
        </h1>
        <p className="text-sm text-surface-400 mt-1">
          {isWinRate
            ? "Win rates between top archetypes. Values above 50% favor the row archetype."
            : "Performance comparison between top archetypes. Positive values mean the row archetype tends to place higher."}
        </p>
      </div>

      {/* Source badge */}
      <div className="flex items-center gap-3">
        <Tooltip content={sourceDescription(data.source)}>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-surface-700 px-3 py-1 text-xs text-surface-300 cursor-help">
            <span
              className={
                data.source === "labs-h2h"
                  ? "h-1.5 w-1.5 rounded-full bg-emerald-400"
                  : data.source === "labs-records"
                    ? "h-1.5 w-1.5 rounded-full bg-amber-400"
                    : "h-1.5 w-1.5 rounded-full bg-surface-400"
              }
            />
            {sourceLabel(data.source)} &middot; {methodologyLabel(data)}{" "}
            &middot; {tournamentCount} tournaments
          </span>
        </Tooltip>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-surface-400">
        {isWinRate ? (
          <>
            <span className="flex items-center gap-1.5">
              <span className="w-4 h-4 rounded bg-emerald-500/40" />
              60%+ (strong)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-4 h-4 rounded bg-emerald-500/25" />
              55-59%
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-4 h-4 rounded bg-emerald-500/10" />
              50-54%
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-4 h-4 rounded bg-red-500/10" />
              46-49%
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-4 h-4 rounded bg-red-500/25" />
              41-45%
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-4 h-4 rounded bg-red-500/40" />
              40% or less (strong)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-4 h-4 rounded bg-surface-700/50" />
              Insufficient data
            </span>
          </>
        ) : (
          <>
            <span className="flex items-center gap-1.5">
              <span className="w-4 h-4 rounded bg-emerald-500/40" />
              Strong advantage (+3 or more)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-4 h-4 rounded bg-emerald-500/15" />
              Slight advantage
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-4 h-4 rounded bg-red-500/15" />
              Slight disadvantage
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-4 h-4 rounded bg-red-500/40" />
              Strong disadvantage (-3 or more)
            </span>
          </>
        )}
      </div>

      {/* Matrix with mobile scroll hint */}
      <div className="relative">
        <div className="overflow-x-auto">
          <MatchupHeatMatrix data={data} />
        </div>
        {/* Gradient fade hint for mobile horizontal scroll */}
        <div className="absolute top-0 right-0 bottom-0 w-8 bg-gradient-to-l from-surface-800 to-transparent pointer-events-none sm:hidden" />
      </div>

      {/* Reading guide */}
      <p className="text-xs text-surface-500 max-w-2xl">
        {isWinRate
          ? "Read left to right: each cell shows how often the row archetype wins against the column archetype. For example, 60% in row A column B means A wins 60% of the time against B. Cells with insufficient data are hidden."
          : "Read left to right: each cell shows the average standing advantage of the row archetype over the column archetype. A value of +2.5 means the row archetype finishes about 2.5 places higher on average when both appear in the same tournament."}
      </p>
    </div>
  );
}
