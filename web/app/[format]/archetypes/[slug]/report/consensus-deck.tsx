import type { ConsensusCard } from "@/app/lib/types";
import { CopyDecklistButton } from "@/app/components/copy-decklist-button";
import { CardLink } from "@/app/components/card-link";

function consensusTextClass(consensus: string): string {
  if (consensus === "core") return "text-slate-100 font-medium";
  if (consensus === "common") return "text-slate-300";
  return "text-slate-500 italic";
}

function ConsensusCardRow({ card, format }: { card: ConsensusCard; format: string }) {
  const isCore = card.consensus === "core";
  const isCommon = card.consensus === "common";

  return (
    <div className="relative py-1.5 px-3 rounded transition-colors hover:bg-surface-700/40 overflow-hidden">
      <div
        className={`absolute inset-y-0 left-0 ${isCore ? "bg-amber-500/10" : isCommon ? "bg-accent/6" : "bg-surface-600/20"}`}
        style={{ width: `${card.weighted_inclusion_pct}%` }}
      />
      <div className="relative flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-mono text-xs w-6 h-5 flex items-center justify-center rounded bg-surface-700 text-slate-300 shrink-0 tabular-nums">
            {card.count}
          </span>
          <CardLink
            name={card.card_name}
            format={format}
            className={`text-sm truncate ${consensusTextClass(card.consensus)}`}
          />
        </div>
        <div className="flex items-center gap-2 ml-2 shrink-0">
          <span
            className={`text-[10px] font-mono tabular-nums ${
              isCore ? "text-amber-500/80" : "text-surface-400"
            }`}
          >
            {card.weighted_inclusion_pct.toFixed(0)}%
          </span>
          <span
            className={`text-[9px] px-1.5 py-0.5 rounded-full ${
              isCore
                ? "bg-amber-500/15 text-amber-400"
                : isCommon
                  ? "bg-accent/10 text-accent/70"
                  : "bg-surface-600/50 text-surface-400"
            }`}
          >
            {card.consensus}
          </span>
        </div>
      </div>
    </div>
  );
}

function CategoryColumn({
  title,
  cards,
  count,
  format,
}: {
  title: string;
  cards: ConsensusCard[];
  count: number;
  format: string;
}) {
  if (cards.length === 0) return null;
  return (
    <div className="bg-surface-800 border border-surface-600 rounded-md overflow-hidden">
      <div className="px-3 py-2 border-b border-surface-600 flex items-center justify-between">
        <h3 className="text-xs font-semibold text-surface-300 uppercase tracking-wider">
          {title}
        </h3>
        <span className="text-[10px] font-mono text-surface-400">
          {count}
        </span>
      </div>
      <div className="p-1.5 space-y-0.5">
        {cards.map((card) => (
          <ConsensusCardRow key={card.card_name} card={card} format={format} />
        ))}
      </div>
    </div>
  );
}

export function ConsensusDeck({
  cards,
  qualityScore,
  totalPokemon,
  totalTrainer,
  totalEnergy,
  format,
}: {
  cards: ConsensusCard[];
  qualityScore: number;
  totalPokemon: number;
  totalTrainer: number;
  totalEnergy: number;
  format: string;
}) {
  const pokemon = cards.filter((c) => c.category === "Pokemon");
  const trainer = cards.filter((c) => c.category === "Trainer");
  const energy = cards.filter((c) => c.category === "Energy");
  const total = totalPokemon + totalTrainer + totalEnergy;

  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <span className="text-xs text-surface-400">
          {total} cards
        </span>
        <span className="text-xs text-surface-500">|</span>
        <span className="text-xs text-surface-400">
          Quality: <span className="font-mono text-slate-300">{qualityScore.toFixed(1)}</span>
        </span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <CategoryColumn title="Pokemon" cards={pokemon} count={totalPokemon} format={format} />
        <CategoryColumn title="Trainer" cards={trainer} count={totalTrainer} format={format} />
        <CategoryColumn title="Energy" cards={energy} count={totalEnergy} format={format} />
      </div>
      <div className="mt-4">
        <CopyDecklistButton cards={cards} />
      </div>
    </div>
  );
}
