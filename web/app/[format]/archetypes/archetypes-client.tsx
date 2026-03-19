"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { TierBadge } from "@/app/components/tier-badge";
import { SpriteRow } from "@/app/components/sprite-row";
import { MetaBarChart } from "@/app/components/meta-bar-chart";
import { DataTable } from "@/app/components/data-table";
import { DateFilter } from "@/app/components/date-filter";
import { useDateFilter, fetchWindowedData } from "@/app/components/date-filter-provider";
import { formatPct, formatPlacement } from "@/app/lib/utils";
import { ArchetypeHeatMatrix } from "@/app/components/archetype-heat-matrix";
import { TrendingUp, TrendingDown, Minus, Sparkles } from "lucide-react";
import { InfoIcon } from "@/app/components/tooltip";
import { MatchupHeatMatrix } from "@/app/components/matchup-heat-matrix";
import type { ArchetypeSummary, MetaData, MatchupMatrixData, OverlapMatrixData, Tier, TimeWindow } from "@/app/lib/types";

function TrendArrow({ trend, delta }: { trend?: string; delta?: number }) {
  if (!trend || trend === "stable") return <Minus className="w-3.5 h-3.5 text-surface-500" />;
  if (trend === "new") return <Sparkles className="w-3.5 h-3.5 text-amber-400" />;
  if (trend === "up") return <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />;
  if (trend === "down") return <TrendingDown className="w-3.5 h-3.5 text-red-400" />;
  return null;
}

export function ArchetypesClient({
  archetypes: initialArchetypes,
  format,
  dateRange,
  overlapMatrix,
  matchupMatrix,
}: {
  archetypes: ArchetypeSummary[];
  format: string;
  dateRange: { start: string; end: string };
  overlapMatrix?: OverlapMatrixData | null;
  matchupMatrix?: MatchupMatrixData | null;
}) {
  const { activeWindow, customRange, setWindow } = useDateFilter();
  const [archetypes, setArchetypes] = useState(initialArchetypes);
  const [loading, setLoading] = useState(false);

  const fetchWindowData = useCallback(
    async (window: TimeWindow) => {
      if (window === "all" || window === "custom") {
        setArchetypes(initialArchetypes);
        return;
      }
      setLoading(true);
      const suffix = window === "7d" ? "-7d" : "-30d";
      const newMeta = await fetchWindowedData<MetaData>(format, "meta.json", suffix);
      if (newMeta) setArchetypes(newMeta.archetypes);
      setLoading(false);
    },
    [format, initialArchetypes],
  );

  useEffect(() => {
    fetchWindowData(activeWindow);
  }, [activeWindow, fetchWindowData]);

  const handleWindowChange = useCallback(
    (window: TimeWindow, range?: { start: string; end: string }) => {
      setWindow(window, range);
    },
    [setWindow],
  );

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-2xl font-bold text-slate-100">
          Archetypes
        </h1>
        <p className="text-sm text-surface-300 mt-1">
          {archetypes.length} archetypes across {archetypes.reduce((sum, a) => sum + a.deck_count, 0).toLocaleString()} decklists
        </p>
      </div>

      <DateFilter
        activeWindow={activeWindow}
        onWindowChange={handleWindowChange}
        dateRange={dateRange}
        customRange={customRange}
      />

      <div className={loading ? "opacity-50 pointer-events-none transition-opacity" : "transition-opacity"}>

      <div className="bg-surface-800 border border-surface-600 rounded-lg p-4 sm:p-6">
        <h2 className="font-display text-sm font-semibold text-slate-200 mb-4">
          Top 20 Meta Shares
        </h2>
        <MetaBarChart data={archetypes} />
      </div>

      {/* Matchup Performance Matrix */}
      {matchupMatrix && matchupMatrix.archetypes.length > 0 && (
        <div className="bg-surface-800 border border-surface-600 rounded-lg p-4 sm:p-6">
          <h2 className="font-display text-sm font-semibold text-slate-200 mb-1 flex items-center gap-1.5">
            Performance Advantage
            <InfoIcon tooltip="Shows how archetypes perform relative to each other when they appear in the same tournaments. A value of +2.0 means the row archetype finishes ~2 standings higher on average. Only matchups with 10+ shared events are shown. Green = favorable, red = unfavorable." />
          </h2>
          <p className="text-xs text-surface-400 mb-2">
            Standing advantage when archetypes co-occur in tournaments (positive = outperforms, min 10 events)
          </p>
          <div className="flex items-center gap-3 text-[10px] text-surface-400 mb-4">
            <div className="flex items-center gap-1.5">
              <div className="flex h-3 w-16 rounded-sm overflow-hidden">
                <div className="flex-1 bg-red-500/40" />
                <div className="flex-1 bg-red-500/25" />
                <div className="flex-1 bg-red-500/10" />
                <div className="flex-1 bg-surface-700/50" />
                <div className="flex-1 bg-emerald-500/10" />
                <div className="flex-1 bg-emerald-500/25" />
                <div className="flex-1 bg-emerald-500/40" />
              </div>
              <span>Unfavorable</span>
              <span className="text-surface-500">/</span>
              <span>Favorable</span>
            </div>
          </div>
          <MatchupHeatMatrix data={matchupMatrix} />
        </div>
      )}

      {/* Archetype Card Overlap Matrix */}
      {overlapMatrix && overlapMatrix.archetypes.length > 0 && (
        <div className="bg-surface-800 border border-surface-600 rounded-lg p-4 sm:p-6">
          <h2 className="font-display text-sm font-semibold text-slate-200 mb-1 flex items-center gap-1.5">
            Card Overlap Matrix
            <InfoIcon tooltip="Shows how similar two archetypes' card pools are using the Jaccard index (shared cards / total unique cards between both decks). Higher values mean more cards in common, which can indicate shared engines or tech choices. Values are percentages (0-100)." />
          </h2>
          <p className="text-xs text-surface-400 mb-2">
            Jaccard similarity of card pools between top archetypes (higher = more shared cards)
          </p>
          <div className="flex items-center gap-3 text-[10px] text-surface-400 mb-4">
            <div className="flex items-center gap-1.5">
              <div className="flex h-3 w-16 rounded-sm overflow-hidden">
                <div className="flex-1 bg-surface-700/50" />
                <div className="flex-1 bg-blue-900/30" />
                <div className="flex-1 bg-blue-800/40" />
                <div className="flex-1 bg-blue-600/40" />
                <div className="flex-1 bg-blue-500/50" />
              </div>
              <span>Low overlap</span>
              <span className="text-surface-500">/</span>
              <span>High overlap</span>
            </div>
          </div>
          <ArchetypeHeatMatrix data={overlapMatrix} format={format} />
        </div>
      )}

      <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
        <DataTable
          data={archetypes}
          searchKey={(a) => a.archetype}
          searchPlaceholder="Search archetypes..."
          columns={[
            {
              key: "tier",
              header: "Tier",
              render: (a) => <TierBadge tier={a.tier as Tier} />,
              sortValue: (a) => {
                const order: Record<string, number> = { S: 0, A: 1, B: 2, C: 3, Rogue: 4 };
                return order[a.tier] ?? 5;
              },
            },
            {
              key: "archetype",
              header: "Archetype",
              render: (a) => (
                <Link
                  href={`/${format}/archetypes/${a.slug}`}
                  className="text-slate-200 hover:text-accent transition-colors inline-flex items-center gap-2"
                >
                  <SpriteRow filenames={a.sprite_filenames ?? []} size={20} />
                  {a.archetype}
                </Link>
              ),
              sortValue: (a) => a.archetype,
            },
            {
              key: "weighted_share",
              header: "Weighted",
              align: "right",
              render: (a) => (
                <span className="font-mono tabular-nums">
                  {formatPct(a.weighted_share ?? a.meta_share)}
                  {a.weighted_share != null && (
                    <span className="text-surface-400 text-xs ml-1">({formatPct(a.meta_share)})</span>
                  )}
                </span>
              ),
              sortValue: (a) => a.weighted_share ?? a.meta_share,
            },
            {
              key: "deck_count",
              header: "Decks",
              align: "right",
              hideOnMobile: true,
              render: (a) => (
                <span className="font-mono tabular-nums text-surface-300">
                  {a.deck_count}
                </span>
              ),
              sortValue: (a) => a.deck_count,
            },
            {
              key: "best_placement",
              header: "Best",
              align: "right",
              hideOnMobile: true,
              render: (a) => (
                <span className="text-surface-300">
                  {formatPlacement(a.best_placement)}
                </span>
              ),
              sortValue: (a) => a.best_placement,
            },
            {
              key: "trend",
              header: "Trend",
              align: "right",
              render: (a) => <TrendArrow trend={a.trend} delta={a.trend_delta} />,
              sortValue: (a) =>
                a.trend === "new" ? 3 : a.trend === "up" ? 2 : a.trend === "down" ? 0 : 1,
            },
          ]}
        />
      </div>

      </div>
    </div>
  );
}
