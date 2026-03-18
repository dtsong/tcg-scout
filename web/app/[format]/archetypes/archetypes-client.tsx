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
import type { ArchetypeSummary, MetaData, Tier, TimeWindow } from "@/app/lib/types";

export function ArchetypesClient({
  archetypes: initialArchetypes,
  format,
  dateRange,
}: {
  archetypes: ArchetypeSummary[];
  format: string;
  dateRange: { start: string; end: string };
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
          {archetypes.length} archetypes tracked across all tiers
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
          ]}
        />
      </div>
      </div>
    </div>
  );
}
