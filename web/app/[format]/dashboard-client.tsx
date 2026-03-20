"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { ArrowRight, TrendingUp, TrendingDown, Trophy, ShoppingCart, Calendar, Zap } from "lucide-react";
import { TierBadge } from "@/app/components/tier-badge";
import { StatCard } from "@/app/components/stat-card";
import { DateFilter } from "@/app/components/date-filter";
import { WelcomeGuide } from "@/app/components/welcome-guide";
import { useDateFilter, fetchWindowedData } from "@/app/components/date-filter-provider";
import { formatPct, daysUntil } from "@/app/lib/utils";
import { InfoIcon } from "@/app/components/tooltip";
import { MetaTimeline } from "@/app/components/meta-timeline";
import type { MetaData, TrendsData, WinningEdgeCard, AceSpec, TimelineData, TimeWindow, MetaEvolutionMovement } from "@/app/lib/types";

interface DashboardClientProps {
  format: string;
  meta: MetaData;
  trends: TrendsData;
  winningEdge: WinningEdgeCard[];
  aceSpecs: AceSpec[];
  timeline?: TimelineData | null;
  metaEvolution?: MetaEvolutionMovement[];
}

export function DashboardClient({
  format,
  meta: initialMeta,
  trends: initialTrends,
  winningEdge: initialWinningEdge,
  aceSpecs: initialAceSpecs,
  timeline,
  metaEvolution = [],
}: DashboardClientProps) {
  const { activeWindow, customRange, setWindow } = useDateFilter();

  const [meta, setMeta] = useState(initialMeta);
  const [trends, setTrends] = useState(initialTrends);
  const [winningEdge, setWinningEdge] = useState(initialWinningEdge);
  const [aceSpecs, setAceSpecs] = useState(initialAceSpecs);
  const [loading, setLoading] = useState(false);

  const fetchWindowData = useCallback(
    async (window: TimeWindow) => {
      if (window === "all" || window === "custom") {
        // Reset to initial data for "all" or "custom" (custom uses client-side filtering)
        setMeta(initialMeta);
        setTrends(initialTrends);
        setWinningEdge(initialWinningEdge);
        setAceSpecs(initialAceSpecs);
        return;
      }

      setLoading(true);
      const suffix = window === "7d" ? "-7d" : "-30d";

      const [newMeta, newTrends, newEdge, newSpecs] = await Promise.all([
        fetchWindowedData<MetaData>(format, "meta.json", suffix),
        fetchWindowedData<TrendsData>(format, "trends.json", suffix),
        fetchWindowedData<WinningEdgeCard[]>(format, "winning-edge.json", suffix),
        fetchWindowedData<AceSpec[]>(format, "ace-specs.json", suffix),
      ]);

      if (newMeta) setMeta(newMeta);
      if (newTrends) setTrends(newTrends);
      if (newEdge) setWinningEdge(newEdge);
      if (newSpecs) setAceSpecs(newSpecs);
      setLoading(false);
    },
    [format, initialMeta, initialTrends, initialWinningEdge, initialAceSpecs],
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

  const rotationDays = daysUntil(meta.rotation_date);
  const topArchetypes = meta.archetypes.filter((a) =>
    ["S", "A", "B"].includes(a.tier),
  );
  const surgingCards = (trends.surging || []).slice(0, 5);
  const decliningCards = (trends.declining || []).slice(0, 5);
  const topEdge = winningEdge.slice(0, 5);
  const topAceSpecs = aceSpecs.slice(0, 5);
  const formatName = meta.format?.name || format;

  return (
    <div className="space-y-6">
      {/* Hero + Stats + Date Filter */}
      <section className="relative rounded-lg bg-surface-800 border border-surface-600 p-5 sm:p-6 scanline-overlay">
        <div className="relative">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
            <p className="text-sm text-surface-300 max-w-xl">
              <span className="text-slate-200 font-medium">{formatName}</span>{" "}is Japan&apos;s post-rotation format. {rotationDays > 0
                ? `These results preview the Standard meta. Set legal internationally on ${meta.rotation_date}.`
                : "This set is now legal internationally."}
            </p>
            <div className="flex items-center gap-1 shrink-0">
              <span className="text-xs text-surface-300 flex items-center gap-1 mr-1">
                <Calendar className="w-3.5 h-3.5" />
                Set Legal
              </span>
              <span className="font-mono text-xl font-medium text-accent tabular-nums">
                {rotationDays > 0 ? `${rotationDays}d` : "Live"}
              </span>
            </div>
          </div>
          <p className="text-xs text-surface-400 mt-2">
            <Link href="/guide#dashboard" className="text-accent hover:text-accent/80 transition-colors">
              How to read the dashboard &rarr;
            </Link>
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
            <div>
              <span className="text-surface-300">Tournaments </span>
              <span className="font-mono font-medium text-slate-100 tabular-nums">{meta.tournament_count.toLocaleString()}</span>
            </div>
            <div>
              <span className="text-surface-300">Decks </span>
              <span className="font-mono font-medium text-slate-100 tabular-nums">{meta.deck_count.toLocaleString()}</span>
            </div>
            <div>
              <span className="text-surface-300">Range </span>
              <span className="font-mono font-medium text-slate-100 tabular-nums">{meta.date_range.start.slice(5)} to {meta.date_range.end.slice(5)}</span>
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-surface-600">
            <DateFilter
              activeWindow={activeWindow}
              onWindowChange={handleWindowChange}
              dateRange={initialMeta.date_range}
              customRange={customRange}
            />
          </div>
        </div>
      </section>

      {/* Welcome Guide (first visit only) */}
      <WelcomeGuide />

      {/* Loading overlay */}
      <div className={loading ? "opacity-50 pointer-events-none transition-opacity" : "transition-opacity"}>
        {/* Quick Insights Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Surging Cards */}
          <section className="bg-surface-800 border border-surface-600 rounded-lg p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-display text-sm font-semibold text-slate-200 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-signal-up" />
                Surging Cards
                <InfoIcon tooltip="Change in usage between the first and second half of the selected time period. +23% means this card appeared in 23 percentage points more decks recently compared to earlier in the same window." />
              </h3>
              <Link href={`/${format}/trends`} className="text-xs text-accent hover:text-accent/80">
                More
              </Link>
            </div>
            <div className="space-y-3">
              {surgingCards.map((card) => (
                <div key={card.card_name} className="flex items-center justify-between">
                  <span className="text-sm text-slate-300 truncate mr-2">{card.card_name}</span>
                  <span className="font-mono text-xs text-signal-up whitespace-nowrap">
                    +{card.delta.toFixed(1)}%
                  </span>
                </div>
              ))}
              {surgingCards.length === 0 && (
                <p className="text-xs text-surface-400">Not enough data for this window</p>
              )}
            </div>
          </section>

          {/* Declining Cards */}
          <section className="bg-surface-800 border border-surface-600 rounded-lg p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-display text-sm font-semibold text-slate-200 flex items-center gap-2">
                <TrendingDown className="w-4 h-4 text-signal-down" />
                Declining Cards
                <InfoIcon tooltip="Change in usage between the first and second half of the selected time period. -18% means this card appeared in 18 percentage points fewer decks recently compared to earlier in the same window." />
              </h3>
              <Link href={`/${format}/trends`} className="text-xs text-accent hover:text-accent/80">
                More
              </Link>
            </div>
            <div className="space-y-3">
              {decliningCards.map((card) => (
                <div key={card.card_name} className="flex items-center justify-between">
                  <span className="text-sm text-slate-300 truncate mr-2">{card.card_name}</span>
                  <span className="font-mono text-xs text-signal-down whitespace-nowrap">
                    {card.delta.toFixed(1)}%
                  </span>
                </div>
              ))}
              {decliningCards.length === 0 && (
                <p className="text-xs text-surface-400">Not enough data for this window</p>
              )}
            </div>
          </section>

          {/* Winning Edge */}
          <section className="bg-surface-800 border border-surface-600 rounded-lg p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-display text-sm font-semibold text-slate-200 flex items-center gap-2">
                <Trophy className="w-4 h-4 text-tier-s" />
                Winning Edge
                <InfoIcon tooltip="How much more often a card appears in 1st-place decks compared to all S/A/B-tier decks in the field. +11% means this card shows up 11 percentage points more in winning decks than in the average S/A/B-tier deck." />
              </h3>
              <Link href={`/${format}/trends`} className="text-xs text-accent hover:text-accent/80">
                More
              </Link>
            </div>
            <div className="space-y-3">
              {topEdge.map((card) => (
                <div key={card.card_name} className="flex items-center justify-between">
                  <span className="text-sm text-slate-300 truncate mr-2">{card.card_name}</span>
                  <span className="font-mono text-xs text-tier-s whitespace-nowrap">
                    +{card.edge.toFixed(1)}%
                  </span>
                </div>
              ))}
              {topEdge.length === 0 && (
                <p className="text-xs text-surface-400">Not enough data for this window</p>
              )}
            </div>
          </section>

          {/* ACE SPEC Distribution */}
          <section className="bg-surface-800 border border-surface-600 rounded-lg p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-display text-sm font-semibold text-slate-200 flex items-center gap-2">
                <ShoppingCart className="w-4 h-4 text-tier-rogue" />
                ACE SPECs
                <InfoIcon tooltip="Percentage of all tournament decks that include each ACE SPEC. Since each deck can only run one ACE SPEC, these percentages show the meta-wide popularity of each choice." />
              </h3>
              <Link href={`/${format}/buylist`} className="text-xs text-accent hover:text-accent/80">
                Buy List
              </Link>
            </div>
            <div className="space-y-3">
              {topAceSpecs.map((spec) => (
                <div key={spec.card_name} className="flex items-center justify-between">
                  <span className="text-sm text-slate-300 truncate mr-2">{spec.card_name}</span>
                  <span className="font-mono text-xs text-surface-300 whitespace-nowrap">
                    {formatPct(spec.usage_pct)}
                  </span>
                </div>
              ))}
              {topAceSpecs.length === 0 && (
                <p className="text-xs text-surface-400">Not enough data for this window</p>
              )}
            </div>
          </section>
        </div>

        {/* Biggest Copy-Count Shifts */}
        {metaEvolution.length > 0 && (
          <div className="mt-6">
            <section className="bg-surface-800 border border-surface-600 rounded-lg p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-display text-sm font-semibold text-slate-200 flex items-center gap-2">
                  <Zap className="w-4 h-4 text-amber-400" />
                  Biggest Copy-Count Shifts
                </h3>
              </div>
              <div className="space-y-3">
                {metaEvolution.map((m, i) => (
                  <div key={i} className="flex items-center justify-between">
                    <div className="flex items-center gap-2 min-w-0 mr-2">
                      {m.direction === "adopted" ? (
                        <TrendingUp className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                      ) : (
                        <TrendingDown className="w-3.5 h-3.5 text-red-400 shrink-0" />
                      )}
                      <span className="text-sm text-slate-300 truncate">{m.card}</span>
                      <span className="text-[10px] text-surface-400 shrink-0">in {m.archetype}</span>
                    </div>
                    <span className="font-mono text-xs text-surface-300 whitespace-nowrap">
                      {m.from_pct.toFixed(0)}% &rarr; {m.to_pct.toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}

        {/* Meta Timeline */}
        {timeline && timeline.weeks.length > 0 && (
          <div className="mt-6">
            <MetaTimeline data={timeline} />
          </div>
        )}

        {/* Tier List Preview */}
        <section className="mt-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-display text-lg font-semibold text-slate-100">
              Meta Tier List
            </h2>
            <Link
              href={`/${format}/archetypes`}
              className="text-sm text-accent hover:text-accent/80 flex items-center gap-1"
            >
              View all <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
          <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-600 text-[11px] text-surface-300 uppercase tracking-wider">
                  <th className="text-left px-3 py-2">Tier</th>
                  <th className="text-left px-3 py-2">Archetype</th>
                  <th className="text-right px-3 py-2">Share</th>
                  <th className="text-right px-3 py-2 hidden sm:table-cell">Decks</th>
                </tr>
              </thead>
              <tbody>
                {topArchetypes.map((arch, i) => (
                  <tr
                    key={arch.slug}
                    className="border-b border-surface-700 hover:bg-surface-700/50 transition-colors animate-row-reveal"
                    style={{ animationDelay: `${i * 20}ms` }}
                  >
                    <td className="px-3 py-2">
                      <TierBadge tier={arch.tier} />
                    </td>
                    <td className="px-3 py-2">
                      <Link
                        href={`/${format}/archetypes/${arch.slug}`}
                        className="text-slate-200 hover:text-accent transition-colors"
                      >
                        {arch.archetype}
                      </Link>
                    </td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums">
                      {formatPct(arch.meta_share)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums text-surface-300 hidden sm:table-cell">
                      {arch.deck_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      {/* Nav Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { href: `/${format}/archetypes`, title: "Archetypes", desc: `${meta.archetypes.length} decks tracked` },
          { href: `/${format}/buylist`, title: "Buy List", desc: "Priority acquisition guide" },
          { href: `/${format}/trends`, title: "Trends", desc: "Usage shifts & winning edge" },
          { href: `/${format}/champions`, title: "Champions League", desc: "CL decklists" },
        ].map(({ href, title, desc }) => (
          <Link
            key={href}
            href={href}
            className="group bg-surface-800 border border-surface-600 rounded-lg p-4 hover:border-surface-400 transition-colors"
          >
            <h3 className="font-display font-semibold text-slate-200 group-hover:text-accent transition-colors">
              {title}
            </h3>
            <p className="text-sm text-surface-300 mt-1">{desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
