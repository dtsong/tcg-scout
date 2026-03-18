"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { ArrowRight, TrendingUp, TrendingDown, Trophy, ShoppingCart, Calendar } from "lucide-react";
import { TierBadge } from "@/app/components/tier-badge";
import { StatCard } from "@/app/components/stat-card";
import { DateFilter } from "@/app/components/date-filter";
import { WelcomeGuide } from "@/app/components/welcome-guide";
import { useDateFilter, fetchWindowedData } from "@/app/components/date-filter-provider";
import { formatPct, daysUntil } from "@/app/lib/utils";
import type { MetaData, TrendsData, WinningEdgeCard, AceSpec, TimeWindow } from "@/app/lib/types";

interface DashboardClientProps {
  format: string;
  meta: MetaData;
  trends: TrendsData;
  winningEdge: WinningEdgeCard[];
  aceSpecs: AceSpec[];
}

export function DashboardClient({
  format,
  meta: initialMeta,
  trends: initialTrends,
  winningEdge: initialWinningEdge,
  aceSpecs: initialAceSpecs,
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
    <div className="space-y-10">
      {/* Hero */}
      <section className="relative rounded-lg bg-surface-800 border border-surface-600 p-6 sm:p-8 scanline-overlay">
        <div className="relative">
          <h1 className="font-display text-3xl sm:text-4xl font-bold text-slate-100">
            Scout
          </h1>
          <p className="mt-2 text-surface-300 max-w-2xl">
            <span className="text-slate-200 font-medium">{formatName}</span>{" "}is Japan&apos;s post-rotation format. These results preview the 2026 Standard meta going live internationally on April 10, 2026.
          </p>
          <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-6">
            <StatCard label="Tournaments" value={meta.tournament_count.toLocaleString()} />
            <StatCard label="Decks Analyzed" value={meta.deck_count.toLocaleString()} />
            <StatCard
              label="Date Range"
              value={`${meta.date_range.start.slice(5)} to ${meta.date_range.end.slice(5)}`}
            />
            <div className="flex flex-col gap-1">
              <span className="text-sm text-surface-300 flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5" />
                Rotation
              </span>
              <span className="font-mono text-2xl font-medium text-accent tabular-nums">
                {rotationDays > 0 ? `${rotationDays}d` : "Live"}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Welcome Guide (first visit only) */}
      <WelcomeGuide />

      {/* Date Filter */}
      <section>
        <DateFilter
          activeWindow={activeWindow}
          onWindowChange={handleWindowChange}
          dateRange={initialMeta.date_range}
          customRange={customRange}
        />
      </section>

      {/* Loading overlay */}
      <div className={loading ? "opacity-50 pointer-events-none transition-opacity" : "transition-opacity"}>
        {/* Tier List Preview */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-display text-xl font-semibold text-slate-100">
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
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-600 text-xs text-surface-300 uppercase tracking-wider">
                  <th className="text-left px-4 py-3">Tier</th>
                  <th className="text-left px-4 py-3">Archetype</th>
                  <th className="text-right px-4 py-3">Meta Share</th>
                  <th className="text-right px-4 py-3 hidden sm:table-cell">Decks</th>
                </tr>
              </thead>
              <tbody>
                {topArchetypes.map((arch, i) => (
                  <tr
                    key={arch.slug}
                    className="border-b border-surface-700 hover:bg-surface-700/50 transition-colors animate-row-reveal"
                    style={{ animationDelay: `${i * 30}ms` }}
                  >
                    <td className="px-4 py-3">
                      <TierBadge tier={arch.tier} />
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/${format}/archetypes/${arch.slug}`}
                        className="text-slate-200 hover:text-accent transition-colors"
                      >
                        {arch.archetype}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-right font-mono tabular-nums">
                      {formatPct(arch.meta_share)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono tabular-nums text-surface-300 hidden sm:table-cell">
                      {arch.deck_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Quick Insights Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mt-10">
          {/* Surging Cards */}
          <section className="bg-surface-800 border border-surface-600 rounded-lg p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-display text-sm font-semibold text-slate-200 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-signal-up" />
                Surging Cards
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
      </div>

      {/* Nav Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
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
