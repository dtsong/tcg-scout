"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { TierBadge } from "@/app/components/tier-badge";
import { SpriteRow } from "@/app/components/sprite-row";
import { MetaBarChart } from "@/app/components/meta-bar-chart";
import { DataTable } from "@/app/components/data-table";
import { DateFilter } from "@/app/components/date-filter";
import { useDateFilter, fetchWindowedData } from "@/app/components/date-filter-provider";
import { cn, formatPct, formatPlacement } from "@/app/lib/utils";
import { ArchetypeHeatMatrix } from "@/app/components/archetype-heat-matrix";
import { InfoIcon } from "@/app/components/tooltip";
import { MatchupHeatMatrix } from "@/app/components/matchup-heat-matrix";
import { TrendingUp, TrendingDown, Minus, Sparkles } from "lucide-react";
import type { ArchetypeSummary, MetaData, MatchupMatrixData, OverlapMatrixData, Tier, TimeWindow } from "@/app/lib/types";

function MatrixLegend({ swatches, lowLabel, highLabel }: {
  swatches: string[];
  lowLabel: string;
  highLabel: string;
}) {
  return (
    <div className="flex items-center gap-3 text-[10px] text-surface-400 mb-4">
      <div className="flex items-center gap-1.5">
        <div className="flex h-3 w-16 rounded-sm overflow-hidden">
          {swatches.map((bg, i) => (
            <div key={i} className={`flex-1 ${bg}`} />
          ))}
        </div>
        <span>{lowLabel}</span>
        <span className="text-surface-500">/</span>
        <span>{highLabel}</span>
      </div>
    </div>
  );
}

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
  type ArchetypeTab = "table" | "matchups" | "overlap";
  const { activeWindow, customRange, setWindow } = useDateFilter();
  const [archetypes, setArchetypes] = useState(initialArchetypes);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<ArchetypeTab>("table");

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
          {archetypes.length} archetypes across {archetypes.reduce((sum, a) => sum + a.deck_count, 0).toLocaleString()} decklists{" "}
          <Link href={`/${format}/guide#archetypes`} className="text-accent hover:text-accent/80 transition-colors">
            How this works &rarr;
          </Link>
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

      {/* Tab bar */}
      <div className="flex items-center gap-1 border-b border-surface-600">
        <button
          onClick={() => setActiveTab("table")}
          className={cn(
            "px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px",
            activeTab === "table"
              ? "border-accent text-accent"
              : "border-transparent text-surface-300 hover:text-slate-200",
          )}
        >
          All Archetypes
          <span className="ml-1.5 text-xs text-surface-400">{archetypes.length}</span>
        </button>
        {matchupMatrix && matchupMatrix.archetypes.length > 0 && (
          <button
            onClick={() => setActiveTab("matchups")}
            className={cn(
              "px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px",
              activeTab === "matchups"
                ? "border-accent text-accent"
                : "border-transparent text-surface-300 hover:text-slate-200",
            )}
          >
            Matchups
          </button>
        )}
        {overlapMatrix && overlapMatrix.archetypes.length > 0 && (
          <button
            onClick={() => setActiveTab("overlap")}
            className={cn(
              "px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px",
              activeTab === "overlap"
                ? "border-accent text-accent"
                : "border-transparent text-surface-300 hover:text-slate-200",
            )}
          >
            Card Overlap
          </button>
        )}
      </div>

      {/* Tab content */}
      {activeTab === "table" && (
        <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
          <DataTable
            data={archetypes}
            searchKey={(a) => a.archetype}
            searchPlaceholder="Search archetypes..."
            pageSizes={[25, 50]}
            defaultPageSize={25}
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
      )}

      {activeTab === "matchups" && matchupMatrix && (
        <div className="bg-surface-800 border border-surface-600 rounded-lg p-4 sm:p-6">
          <h2 className="font-display text-sm font-semibold text-slate-200 mb-1 flex items-center gap-1.5">
            Performance Advantage
            <InfoIcon tooltip="Shows how archetypes perform relative to each other when they appear in the same tournaments. A value of +2.0 means the row archetype finishes 2 standings better (lower place number) on average. Cells are blank when fewer than 10 shared tournaments exist. Green = favorable, red = unfavorable." />
          </h2>
          <p className="text-xs text-surface-400 mb-2">
            Standing advantage when archetypes co-occur in tournaments (positive = outperforms, min 10 tournaments)
          </p>
          <MatrixLegend
            swatches={["bg-red-500/40", "bg-red-500/25", "bg-red-500/10", "bg-surface-700/50", "bg-emerald-500/10", "bg-emerald-500/25", "bg-emerald-500/40"]}
            lowLabel="Unfavorable"
            highLabel="Favorable"
          />
          <MatchupHeatMatrix data={matchupMatrix} />
        </div>
      )}

      {activeTab === "overlap" && overlapMatrix && (
        <div className="bg-surface-800 border border-surface-600 rounded-lg p-4 sm:p-6">
          <h2 className="font-display text-sm font-semibold text-slate-200 mb-1 flex items-center gap-1.5">
            Card Overlap Matrix
            <InfoIcon tooltip="Shows how similar two archetypes' core card pools are using the Jaccard index. Based on cards appearing in 30%+ of each archetype's decks. Higher values mean more shared staples. Values are percentages (0-100)." />
          </h2>
          <p className="text-xs text-surface-400 mb-2">
            Jaccard similarity of core card pools between top archetypes (higher = more shared cards)
          </p>
          <MatrixLegend
            swatches={["bg-surface-700/50", "bg-blue-900/30", "bg-blue-800/40", "bg-blue-600/40", "bg-blue-500/50"]}
            lowLabel="Low overlap"
            highLabel="High overlap"
          />
          <ArchetypeHeatMatrix data={overlapMatrix} format={format} />
        </div>
      )}

      </div>
    </div>
  );
}
