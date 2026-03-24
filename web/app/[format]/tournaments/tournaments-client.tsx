"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight, TrendingUp, ExternalLink } from "lucide-react";
import { cn } from "@/app/lib/utils";
import { formatPlacement } from "@/app/lib/utils";
import { SpriteRow } from "@/app/components/sprite-row";
import { TierBadge } from "@/app/components/tier-badge";
import { DateFilter } from "@/app/components/date-filter";
import {
  useDateFilter,
  fetchWindowedData,
} from "@/app/components/date-filter-provider";
import type {
  CityLeagueIndex,
  CityLeagueTournament,
  Tier,
  TimeWindow,
} from "@/app/lib/types";

const tierColors: Record<string, string> = {
  S: "#f59e0b",
  A: "#14b8a6",
  B: "#3b82f6",
  C: "#64748b",
  Rogue: "#a855f7",
};

const distributionPalette = [
  "#f59e0b", "#14b8a6", "#3b82f6", "#a855f7", "#ef4444",
  "#22c55e", "#ec4899", "#f97316",
];

function daysSince(dateStr: string): number {
  const d = new Date(dateStr);
  const now = new Date();
  return Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatDateShort(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "2-digit", day: "2-digit" });
}

/** Group tournaments by date, sorted descending. */
function groupByDate(
  tournaments: CityLeagueTournament[],
): { date: string; tournaments: CityLeagueTournament[] }[] {
  const groups = new Map<string, CityLeagueTournament[]>();
  for (const t of tournaments) {
    const existing = groups.get(t.date);
    if (existing) {
      existing.push(t);
    } else {
      groups.set(t.date, [t]);
    }
  }
  return Array.from(groups.entries())
    .sort((a, b) => b[0].localeCompare(a[0]))
    .map(([date, tournaments]) => ({ date, tournaments }));
}

function RecencyDot({ dateStr }: { dateStr: string }) {
  const days = daysSince(dateStr);
  if (days > 7) return null;
  return <span className="w-1.5 h-1.5 bg-accent rounded-full shrink-0" />;
}

function DistributionBar({
  distribution,
}: {
  distribution: CityLeagueTournament["archetype_distribution"];
}) {
  if (!distribution || distribution.length === 0) return null;

  return (
    <div className="flex h-5 w-full rounded overflow-hidden">
      {distribution.slice(0, 8).map((entry, i) => {
        const color = distributionPalette[i % distributionPalette.length];
        return (
          <div
            key={i}
            className="h-full transition-all"
            style={{
              width: `${Math.max(entry.share * 100, 2)}%`,
              backgroundColor: color,
              opacity: 0.6 + i * -0.05,
            }}
            title={`${entry.archetype}: ${(entry.share * 100).toFixed(1)}%`}
          />
        );
      })}
    </div>
  );
}

function TournamentRow({
  tournament,
  format,
}: {
  tournament: CityLeagueTournament;
  format: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const days = daysSince(tournament.date);
  const winner = tournament.top_finishers[0];

  return (
    <>
      <div
        className={cn(
          "flex items-center gap-3 px-4 py-3 border-b border-surface-700 hover:bg-surface-700/50 transition-colors cursor-pointer",
          days > 30 && "opacity-75",
        )}
        onClick={() => setExpanded(!expanded)}
      >
        {/* Expand chevron */}
        <div className="shrink-0 w-4">
          {expanded ? (
            <ChevronDown className="w-3.5 h-3.5 text-surface-400" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-surface-400" />
          )}
        </div>

        {/* Recency dot + date */}
        <div className="flex items-center gap-1.5 shrink-0 w-16 sm:w-20">
          <RecencyDot dateStr={tournament.date} />
          <span className="font-mono text-xs text-surface-300 tabular-nums">
            {formatDateShort(tournament.date)}
          </span>
        </div>

        {/* Tournament name + prefecture */}
        <div className="flex-1 min-w-0">
          <span className="text-sm text-slate-200 truncate block">
            {tournament.name}
          </span>
          {tournament.prefecture && (
            <span className="text-xs text-surface-400 sm:hidden block">
              {tournament.prefecture}
            </span>
          )}
        </div>

        {/* Prefecture (desktop) */}
        {tournament.prefecture && (
          <span className="text-xs text-surface-400 hidden sm:block shrink-0 w-24 text-right">
            {tournament.prefecture}
          </span>
        )}

        {/* Player count */}
        <span className="font-mono text-xs text-surface-400 tabular-nums shrink-0 w-12 text-right hidden sm:block">
          {tournament.player_count ?? "--"}
        </span>

        {/* Winner sprites */}
        <div className="shrink-0">
          {winner?.sprite_filenames && winner.sprite_filenames.length > 0 ? (
            <SpriteRow filenames={winner.sprite_filenames} size={20} />
          ) : (
            <span className="text-xs text-surface-400">--</span>
          )}
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="bg-surface-700/30 border-b border-surface-700 px-4 py-4 space-y-4">
          {/* Top 4 finishers */}
          {tournament.top_finishers.length > 0 && (
            <div className="space-y-1.5">
              <h4 className="text-xs font-semibold text-surface-300 uppercase tracking-wider mb-2">
                Top 4
              </h4>
              {tournament.top_finishers.map((f) => (
                <div
                  key={f.standing}
                  className="flex items-center gap-3 py-1"
                >
                  <span
                    className={cn(
                      "font-mono text-xs tabular-nums w-8",
                      f.standing === 1 ? "text-accent font-bold" : "text-surface-300",
                    )}
                  >
                    {formatPlacement(f.standing)}
                  </span>
                  {f.sprite_filenames && f.sprite_filenames.length > 0 && (
                    <SpriteRow filenames={f.sprite_filenames} size={20} />
                  )}
                  <Link
                    href={`/${format}/archetypes/${f.slug}`}
                    className="text-sm text-slate-200 hover:text-accent transition-colors"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {f.archetype}
                  </Link>
                  {f.tier && (
                    <TierBadge
                      tier={f.tier as Tier}
                      className="w-5 h-5 text-[10px]"
                    />
                  )}
                  <span className="text-xs text-surface-400 hidden sm:inline">
                    {f.player_name}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Archetype distribution */}
          {tournament.archetype_distribution.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-surface-300 uppercase tracking-wider mb-2">
                Archetype Distribution
              </h4>
              <div className="space-y-1">
                {tournament.archetype_distribution.slice(0, 6).map((entry) => (
                  <div
                    key={entry.slug}
                    className="flex items-center gap-2 text-xs"
                  >
                    {entry.sprite_filenames &&
                      entry.sprite_filenames.length > 0 && (
                        <SpriteRow filenames={entry.sprite_filenames} size={16} />
                      )}
                    <Link
                      href={`/${format}/archetypes/${entry.slug}`}
                      className="text-slate-300 hover:text-accent transition-colors"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {entry.archetype}
                    </Link>
                    <span className="font-mono text-surface-400 tabular-nums">
                      {entry.count} ({(entry.share * 100).toFixed(1)}%)
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Source link */}
          {tournament.source_url && (
            <a
              href={tournament.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-accent hover:text-accent/80 transition-colors"
              onClick={(e) => e.stopPropagation()}
            >
              View full results
              <ExternalLink className="w-3 h-3" />
            </a>
          )}
        </div>
      )}
    </>
  );
}

export function TournamentsClient({
  format,
  index: initialIndex,
  dateRange,
}: {
  format: string;
  index: CityLeagueIndex;
  dateRange: { start: string; end: string };
}) {
  const { activeWindow, customRange, setWindow } = useDateFilter();
  const [index, setIndex] = useState(initialIndex);
  const [loading, setLoading] = useState(false);

  const fetchWindowData = useCallback(
    async (window: TimeWindow) => {
      if (window === "all") {
        setIndex(initialIndex);
        return;
      }
      if (window === "custom" && customRange) {
        const filtered = initialIndex.tournaments.filter(
          (t) => t.date >= customRange.start && t.date <= customRange.end,
        );
        setIndex({
          ...initialIndex,
          tournaments: filtered,
          tournament_count: filtered.length,
          deck_count: filtered.reduce((sum, t) => sum + (t.player_count || 0), 0),
        });
        return;
      }
      if (window === "custom") {
        setIndex(initialIndex);
        return;
      }
      setLoading(true);
      try {
        const suffix = window === "7d" ? "-7d" : "-30d";
        const newIndex = await fetchWindowedData<CityLeagueIndex>(
          format,
          "city-league-index.json",
          suffix,
        );
        if (newIndex) {
          setIndex(newIndex);
        } else {
          setIndex(initialIndex);
          setWindow("all");
        }
      } catch (err) {
        console.error("[tournaments] Failed to load windowed data:", err);
        setIndex(initialIndex);
        setWindow("all");
      } finally {
        setLoading(false);
      }
    },
    [format, initialIndex, customRange],
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

  const dateGroups = useMemo(() => groupByDate(index.tournaments), [index.tournaments]);

  // Compute "this week" count
  const thisWeekCount = useMemo(
    () => index.tournaments.filter((t) => daysSince(t.date) <= 7).length,
    [index.tournaments],
  );

  // Find most winning archetype
  const topWinner = index.recent_winners[0];

  return (
    <div className="space-y-6">
      {/* Hero header */}
      <section className="relative rounded-md bg-surface-800 border border-surface-600 p-5 sm:p-6 scanline-overlay">
        <div className="relative">
          <h1 className="font-display text-2xl font-bold text-slate-100">
            Tournaments
          </h1>
          <p className="text-sm text-surface-300 mt-1">
            City League results across Japan, sorted by date.
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
            <div>
              <span className="text-surface-300">Tournaments </span>
              <span className="font-mono font-medium text-slate-100 tabular-nums">
                {index.tournament_count.toLocaleString()}
              </span>
            </div>
            <div>
              <span className="text-surface-300">This Week </span>
              <span className="font-mono font-medium text-slate-100 tabular-nums">
                {thisWeekCount}
              </span>
            </div>
            <div>
              <span className="text-surface-300">Decks </span>
              <span className="font-mono font-medium text-slate-100 tabular-nums">
                {index.deck_count.toLocaleString()}
              </span>
            </div>
            {topWinner && (
              <div className="flex items-center gap-1.5">
                <span className="text-surface-300">Latest Winner </span>
                {topWinner.sprite_filenames &&
                  topWinner.sprite_filenames.length > 0 && (
                    <SpriteRow filenames={topWinner.sprite_filenames} size={20} />
                  )}
                <Link
                  href={`/${format}/archetypes/${topWinner.slug}`}
                  className="font-medium text-slate-100 hover:text-accent transition-colors"
                >
                  {topWinner.archetype}
                </Link>
              </div>
            )}
          </div>

          <div className="mt-4 pt-3 border-t border-surface-600">
            <DateFilter
              activeWindow={activeWindow}
              onWindowChange={handleWindowChange}
              dateRange={dateRange}
              customRange={customRange}
            />
          </div>
        </div>
      </section>

      {/* Rising archetypes */}
      {index.rising_archetypes.length > 0 && (
        <section className="flex flex-wrap gap-3">
          {index.rising_archetypes.slice(0, 5).map((arch) => (
            <Link
              key={arch.slug}
              href={`/${format}/archetypes/${arch.slug}`}
              className="flex items-center gap-2 px-3 py-2 rounded-md bg-surface-800 border border-surface-600 hover:border-surface-500 transition-colors"
            >
              {arch.sprite_filenames && arch.sprite_filenames.length > 0 && (
                <SpriteRow filenames={arch.sprite_filenames} size={20} />
              )}
              <span className="text-sm text-slate-200">{arch.archetype}</span>
              {arch.tier && (
                <TierBadge
                  tier={arch.tier as Tier}
                  className="w-5 h-5 text-[10px]"
                />
              )}
              <span className="flex items-center gap-0.5 text-xs font-mono text-green-400">
                <TrendingUp className="w-3 h-3" />
                +{arch.trend_delta.toFixed(1)}
              </span>
            </Link>
          ))}
        </section>
      )}

      {/* Tournament list */}
      <div
        className={cn(
          "transition-opacity",
          loading && "opacity-50 pointer-events-none",
        )}
      >
        <div className="rounded-md bg-surface-800 border border-surface-600 overflow-hidden">
          {/* Column headers (desktop) */}
          <div className="hidden sm:flex items-center gap-3 px-4 py-2 border-b border-surface-600 text-xs text-surface-400 uppercase tracking-wider font-semibold">
            <div className="w-4" />
            <div className="w-20">Date</div>
            <div className="flex-1">Tournament</div>
            <div className="w-24 text-right">Prefecture</div>
            <div className="w-12 text-right">Players</div>
            <div className="shrink-0">Winner</div>
          </div>

          {dateGroups.map((group) => (
            <div key={group.date}>
              {/* Date group header */}
              <div className="sticky top-14 z-10 flex items-center gap-2 px-4 py-2 bg-surface-700/90 backdrop-blur-sm border-b border-surface-600">
                <span className="text-sm font-medium text-slate-200">
                  {formatDate(group.date)}
                </span>
                <span className="text-xs text-surface-400 font-mono">
                  {group.tournaments.length}{" "}
                  {group.tournaments.length === 1
                    ? "tournament"
                    : "tournaments"}
                </span>
              </div>

              {/* Tournament rows */}
              {group.tournaments.map((t) => (
                <TournamentRow key={t.id} tournament={t} format={format} />
              ))}
            </div>
          ))}

          {dateGroups.length === 0 && (
            <div className="text-center py-12 text-surface-300">
              No tournaments found for this time window.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
