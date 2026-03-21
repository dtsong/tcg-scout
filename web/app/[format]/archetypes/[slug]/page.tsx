import Link from "next/link";
import { getArchetype, getArchetypeReport, getArchetypeSlugs, getFormats, getOptimal60Index } from "@/app/lib/data";
import { TierBadge } from "@/app/components/tier-badge";
import { SpriteRow } from "@/app/components/sprite-row";
import { StatCard } from "@/app/components/stat-card";
import { ArchetypeRadar } from "@/app/components/archetype-radar";
import { EvolutionTimeline } from "@/app/components/evolution-timeline";
import { PerformanceTrendline } from "@/app/components/performance-trendline";
import { VariantBreakdown } from "@/app/components/variant-breakdown";
import { formatPct, formatPlacement } from "@/app/lib/utils";
import type { ArchetypeCard } from "@/app/lib/types";
import { Top4CardStats } from "@/app/components/top4-card-stats";
import { ResultsTable } from "./results-table";

export function generateStaticParams() {
  const formats = getFormats();
  const params: { format: string; slug: string }[] = [];
  for (const fmt of formats) {
    const slugs = getArchetypeSlugs(fmt.slug);
    for (const slug of slugs) {
      params.push({ format: fmt.slug, slug });
    }
  }
  return params;
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

function CardRow({ card, isCore }: { card: ArchetypeCard; isCore: boolean }) {
  const copies = card.avg_copies % 1 === 0
    ? card.avg_copies.toString()
    : card.avg_copies.toFixed(1);
  return (
    <div className="relative py-2 px-3 rounded transition-colors hover:bg-surface-700/40 overflow-hidden">
      {/* Inclusion progress bar background */}
      <div
        className={`absolute inset-y-0 left-0 ${isCore ? "bg-accent/8" : "bg-surface-600/30"}`}
        style={{ width: `${card.inclusion_pct}%` }}
      />
      <div className="relative flex items-center justify-between">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="font-mono text-xs w-7 h-6 flex items-center justify-center rounded bg-surface-700 text-slate-300 shrink-0 tabular-nums">
            {copies}
          </span>
          <span className={`text-sm truncate ${isCore ? "text-slate-200" : "text-slate-400"}`}>
            {card.card_name}
          </span>
        </div>
        <span className={`text-xs font-mono ml-3 shrink-0 tabular-nums ${
          card.inclusion_pct >= 80 ? "text-accent/70" : "text-surface-400"
        }`}>
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
    <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
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

export default async function ArchetypeDetailPage({
  params,
}: {
  params: Promise<{ format: string; slug: string }>;
}) {
  const { format, slug } = await params;
  const arch = getArchetype(format, slug);
  const hasReport = getArchetypeReport(format, slug) !== null;
  const optimal60Index = getOptimal60Index(format);
  const hasOptimal60 = optimal60Index?.archetypes.some((a) => a.slug === slug) ?? false;

  const coreNames = new Set(arch.core_cards.map((c) => c.card_name));
  const { pokemon, trainer, energy } = groupByCategory(arch.all_cards);

  // Count total cards (avg copies summed)
  const totalCards = (cat: ArchetypeCard[]) =>
    cat.reduce((sum, c) => sum + Math.round(c.avg_copies), 0);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <TierBadge tier={arch.tier} />
          <SpriteRow filenames={arch.sprite_filenames ?? []} size={32} />
          <h1 className="font-display text-2xl font-bold text-slate-100">
            {arch.archetype}
          </h1>
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
          <StatCard label="Best Finish" value={formatPlacement(arch.best_placement)} />
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
              href={`/${format}/optimal-60`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-teal-400 bg-teal-500/10 hover:bg-teal-500/20 border border-teal-500/20 rounded-md transition-colors"
            >
              View Optimal 60
            </Link>
          )}
        </div>
      </div>

      {/* Performance Trendline */}
      {arch.weekly_shares && arch.weekly_shares.length >= 3 && (
        <PerformanceTrendline data={arch.weekly_shares} />
      )}

      {/* Variants */}
      {arch.variants && arch.variants.length >= 2 && (
        <VariantBreakdown variants={arch.variants} deckCount={arch.deck_count} />
      )}

      {/* Radar */}
      {arch.radar && <ArchetypeRadar radar={arch.radar} />}

      {/* Decklist */}
      <section>
        <h2 className="font-display text-lg font-semibold text-slate-100 mb-1">
          Decklist
        </h2>
        <p className="text-xs text-surface-400 mb-4">
          Averaged across {arch.deck_count} {arch.deck_count === 1 ? "deck" : "decks"}.
          Bold = core (80%+), dimmed = flex.
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

      {/* Top 4 Card Analysis */}
      {arch.top4_card_stats && arch.top4_card_stats.length > 0 && (
        <Top4CardStats
          cards={arch.top4_card_stats}
          sampleSize={arch.top4_sample_size ?? 0}
          lowSample={arch.top4_low_sample ?? true}
          deckCount={arch.deck_count}
          format={format}
        />
      )}

      {/* List Evolution */}
      {arch.evolution && arch.evolution.length > 0 && (
        <EvolutionTimeline evolution={arch.evolution} />
      )}

      {/* Results */}
      {arch.results && arch.results.length > 0 && (
        <ResultsTable results={arch.results} />
      )}
    </div>
  );
}
