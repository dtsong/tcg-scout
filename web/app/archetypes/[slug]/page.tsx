import { getArchetype, getArchetypeSlugs } from "@/app/lib/data";
import { TierBadge } from "@/app/components/tier-badge";
import { SpriteRow } from "@/app/components/sprite-row";
import { StatCard } from "@/app/components/stat-card";
import { formatPct, formatPlacement } from "@/app/lib/utils";
import type { ArchetypeCard } from "@/app/lib/types";
import { ResultsTable } from "./results-table";

export function generateStaticParams() {
  return getArchetypeSlugs().map((slug) => ({ slug }));
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
  const copies = Math.round(card.avg_copies);
  return (
    <div
      className={`flex items-center justify-between py-1.5 px-2 rounded transition-colors hover:bg-surface-700/40 ${
        isCore ? "" : "opacity-50"
      }`}
    >
      <div className="flex items-center gap-2 min-w-0">
        <span
          className="font-mono text-xs w-5 h-5 flex items-center justify-center rounded bg-surface-700 text-slate-300 shrink-0"
        >
          {copies}
        </span>
        <span className="text-sm text-slate-200 truncate">{card.card_name}</span>
      </div>
      {card.inclusion_pct < 100 && (
        <span className="text-[10px] font-mono text-surface-400 ml-2 shrink-0">
          {card.inclusion_pct.toFixed(0)}%
        </span>
      )}
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
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const arch = getArchetype(slug);

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
          <StatCard label="Decks" value={arch.deck_count} />
          <StatCard label="Best Finish" value={formatPlacement(arch.best_placement)} />
          <StatCard label="Core Cards" value={arch.core_cards.length} />
        </div>
      </div>

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

      {/* Results */}
      {arch.results && arch.results.length > 0 && (
        <ResultsTable results={arch.results} />
      )}
    </div>
  );
}
