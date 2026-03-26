"use client";

import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { useCallback, Suspense } from "react";
import Link from "next/link";
import type { ArchetypeDetail, ArchetypeCard, MatchupMatrixData } from "@/app/lib/types";
import { TierBadge } from "@/app/components/tier-badge";
import { SpriteRow } from "@/app/components/sprite-row";
import { StatCard } from "@/app/components/stat-card";
import { ShareButton } from "@/app/components/share-button";
import { ArchetypeRadar } from "@/app/components/archetype-radar";
import { EvolutionTimeline } from "@/app/components/evolution-timeline";
import { PerformanceTrendline } from "@/app/components/performance-trendline";
import { VariantBreakdown } from "@/app/components/variant-breakdown";
import { Top4CardStats } from "@/app/components/top4-card-stats";
import { CardLink } from "@/app/components/card-link";
import { KeyMatchups } from "@/app/components/key-matchups";
import { Tabs } from "@/app/components/tabs";
import { formatPct, formatPlacement } from "@/app/lib/utils";
import { ResultsTable } from "./results-table";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "decklist", label: "Decklist" },
  { id: "matchups", label: "Matchups" },
  { id: "results", label: "Results" },
] as const;

type TabId = (typeof TABS)[number]["id"];

const VALID_TABS = new Set<string>(TABS.map((t) => t.id));

function isValidTab(tab: string | null): tab is TabId {
  return tab !== null && VALID_TABS.has(tab);
}

function CardRow({ card, isCore }: { card: ArchetypeCard; isCore: boolean }) {
  const copies =
    card.avg_copies % 1 === 0
      ? card.avg_copies.toString()
      : card.avg_copies.toFixed(1);
  return (
    <div className="relative py-2 px-3 rounded transition-colors hover:bg-surface-700/40 overflow-hidden">
      <div
        className={`absolute inset-y-0 left-0 ${isCore ? "bg-accent/8" : "bg-surface-600/30"}`}
        style={{ width: `${card.inclusion_pct}%` }}
      />
      <div className="relative flex items-center justify-between">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="font-mono text-xs w-7 h-6 flex items-center justify-center rounded bg-surface-700 text-slate-300 shrink-0 tabular-nums">
            {copies}
          </span>
          <CardLink
            name={card.card_name}
            className={`text-sm truncate ${isCore ? "text-slate-200" : "text-slate-400"}`}
          />
        </div>
        <span
          className={`text-xs font-mono ml-3 shrink-0 tabular-nums ${
            card.inclusion_pct >= 80 ? "text-accent/70" : "text-surface-400"
          }`}
        >
          {card.inclusion_pct.toFixed(0)}%
        </span>
      </div>
    </div>
  );
}

function DeckColumn({
  title,
  cards,
  coreNames,
  count,
}: {
  title: string;
  cards: ArchetypeCard[];
  coreNames: Set<string>;
  count: number;
}) {
  if (cards.length === 0) return null;
  return (
    <div className="bg-surface-800 border border-surface-600 rounded-md overflow-hidden">
      <div className="px-3 py-2 border-b border-surface-600 flex items-center justify-between">
        <h3 className="text-xs font-semibold text-surface-300 uppercase tracking-wider">
          {title}
        </h3>
        <span className="text-[10px] font-mono text-surface-400">{count}</span>
      </div>
      <div className="p-1.5 space-y-0.5">
        {cards.map((card) => (
          <CardRow
            key={card.card_name}
            card={card}
            isCore={coreNames.has(card.card_name)}
          />
        ))}
      </div>
    </div>
  );
}

function groupByCategory(cards: ArchetypeCard[]) {
  const pokemon: ArchetypeCard[] = [];
  const trainer: ArchetypeCard[] = [];
  const energy: ArchetypeCard[] = [];
  for (const card of cards) {
    switch (card.category) {
      case "Energy":
        energy.push(card);
        break;
      case "Trainer":
        trainer.push(card);
        break;
      default:
        pokemon.push(card);
    }
  }
  return { pokemon, trainer, energy };
}

function ArchetypeDetailInner({
  arch,
  matchupData,
  format,
  slug,
  hasReport,
  hasOptimal60,
}: {
  arch: ArchetypeDetail;
  matchupData: MatchupMatrixData | null;
  format: string;
  slug: string;
  hasReport: boolean;
  hasOptimal60: boolean;
}) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const rawTab = searchParams.get("tab");
  const activeTab: TabId = isValidTab(rawTab) ? rawTab : "overview";

  const handleTabChange = useCallback(
    (id: string) => {
      const params = new URLSearchParams(searchParams.toString());
      if (id === "overview") {
        params.delete("tab");
      } else {
        params.set("tab", id);
      }
      const qs = params.toString();
      router.replace(`${pathname}${qs ? `?${qs}` : ""}`, { scroll: false });
    },
    [searchParams, router, pathname],
  );

  const coreNames = new Set(arch.core_cards.map((c) => c.card_name));
  const { pokemon, trainer, energy } = groupByCategory(arch.all_cards);
  const totalCards = (cat: ArchetypeCard[]) =>
    cat.reduce((sum, c) => sum + Math.round(c.avg_copies), 0);

  return (
    <div className="space-y-6">
      {/* Header -- always visible */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <TierBadge tier={arch.tier} />
          <SpriteRow filenames={arch.sprite_filenames ?? []} size={32} />
          <h1 className="font-display text-2xl font-bold text-slate-100">
            {arch.archetype}
          </h1>
          <ShareButton
            title={`${arch.archetype} - Scout`}
            text={`${arch.archetype} (${arch.tier} tier) - ${formatPct(arch.meta_share)} meta share`}
            pageType="archetype"
            className="ml-auto"
          />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 mt-4">
          <StatCard label="Meta Share" value={formatPct(arch.meta_share)} />
          {arch.weighted_share != null ? (
            <StatCard
              label="Weighted Share"
              value={formatPct(arch.weighted_share)}
              tooltip="Placements weighted by finish: 1st = 3x, 2nd = 2.5x, 3rd-4th = 2x, 5th-8th = 1.5x, 9th-16th = 1.2x, 17th+ = 1x. Surfaces decks that win, not just decks that show up."
            />
          ) : (
            <StatCard label="Decks" value={arch.deck_count} />
          )}
          <StatCard
            label="Best Finish"
            value={formatPlacement(arch.best_placement)}
          />
          <StatCard label="Core Cards" value={arch.core_cards.length} />
        </div>
        <div className="flex flex-wrap gap-2 mt-4">
          {hasReport && (
            <Link
              href={`/${format}/archetypes/${slug}/report`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-amber-400 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20 rounded-md transition-colors"
            >
              View Deep Dive Report
            </Link>
          )}
          {hasOptimal60 && (
            <Link
              href={`/${format}/optimal-60?deck=${slug}`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-teal-400 bg-teal-500/10 hover:bg-teal-500/20 border border-teal-500/20 rounded-md transition-colors"
            >
              View Optimal 60
            </Link>
          )}
        </div>
      </div>

      {/* Tab bar */}
      <Tabs
        tabs={[...TABS]}
        activeTab={activeTab}
        onTabChange={handleTabChange}
      />

      {/* Tab content */}
      <div>
        {activeTab === "overview" && (
          <div className="space-y-8">
            {arch.weekly_shares && arch.weekly_shares.length >= 3 && (
              <PerformanceTrendline data={arch.weekly_shares} />
            )}
            {arch.variants && arch.variants.length >= 2 && (
              <VariantBreakdown
                variants={arch.variants}
                deckCount={arch.deck_count}
              />
            )}
            {arch.radar && <ArchetypeRadar radar={arch.radar} />}
            {matchupData && (
              <KeyMatchups
                data={matchupData}
                archetype={arch.archetype}
                format={format}
              />
            )}
          </div>
        )}

        {activeTab === "decklist" && (
          <div className="space-y-8">
            <section>
              <h2 className="font-display text-lg font-semibold text-slate-100 mb-1">
                Decklist
              </h2>
              <p className="text-xs text-surface-400 mb-4">
                Averaged across {arch.deck_count}{" "}
                {arch.deck_count === 1 ? "deck" : "decks"}. Bold = core (75%+),
                dimmed = flex.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <DeckColumn
                  title="Pokemon"
                  cards={pokemon}
                  coreNames={coreNames}
                  count={totalCards(pokemon)}
                />
                <DeckColumn
                  title="Trainer"
                  cards={trainer}
                  coreNames={coreNames}
                  count={totalCards(trainer)}
                />
                <DeckColumn
                  title="Energy"
                  cards={energy}
                  coreNames={coreNames}
                  count={totalCards(energy)}
                />
              </div>
            </section>
            {arch.top4_card_stats && arch.top4_card_stats.length > 0 && (
              <Top4CardStats
                cards={arch.top4_card_stats}
                sampleSize={arch.top4_sample_size ?? 0}
                lowSample={arch.top4_low_sample ?? true}
                deckCount={arch.deck_count}
                format={format}
              />
            )}
          </div>
        )}

        {activeTab === "matchups" && (
          <div className="space-y-8">
            {matchupData ? (
              <KeyMatchups
                data={matchupData}
                archetype={arch.archetype}
                format={format}
              />
            ) : (
              <p className="text-surface-400 text-sm">
                No matchup data available for this format.
              </p>
            )}
          </div>
        )}

        {activeTab === "results" && (
          <div className="space-y-8">
            {arch.evolution && arch.evolution.length > 0 && (
              <EvolutionTimeline evolution={arch.evolution} />
            )}
            {arch.results && arch.results.length > 0 ? (
              <ResultsTable results={arch.results} />
            ) : (
              <p className="text-surface-400 text-sm">
                No tournament results recorded.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function ArchetypeDetailClient(props: {
  arch: ArchetypeDetail;
  matchupData: MatchupMatrixData | null;
  format: string;
  slug: string;
  hasReport: boolean;
  hasOptimal60: boolean;
}) {
  return (
    <Suspense fallback={null}>
      <ArchetypeDetailInner {...props} />
    </Suspense>
  );
}
