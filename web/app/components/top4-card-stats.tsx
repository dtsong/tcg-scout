"use client";

import { useState } from "react";
import Link from "next/link";
import type { TopPerformerCard } from "@/app/lib/types";
import { slugify } from "@/app/lib/utils";

type CategoryFilter = "all" | "Pokemon" | "Trainer" | "Energy";

const categories: { label: string; value: CategoryFilter }[] = [
  { label: "All", value: "all" },
  { label: "Pokemon", value: "Pokemon" },
  { label: "Trainer", value: "Trainer" },
  { label: "Energy", value: "Energy" },
];

function DeltaBadge({ delta }: { delta: number }) {
  if (delta === 0) {
    return <span className="text-xs font-mono text-surface-400 tabular-nums">0.0</span>;
  }
  const positive = delta > 0;
  return (
    <span
      className={`text-xs font-mono tabular-nums ${
        positive ? "text-emerald-400" : "text-red-400"
      }`}
    >
      {positive ? "+" : ""}
      {delta.toFixed(1)}
    </span>
  );
}

function TopCardRow({ card, format }: { card: TopPerformerCard; format: string }) {
  const copies =
    card.avg_copies % 1 === 0
      ? card.avg_copies.toString()
      : card.avg_copies.toFixed(1);
  const absDelta = Math.abs(card.delta_vs_field);
  const barWidth = Math.min(absDelta * 3, 100);
  const positive = card.delta_vs_field > 0;

  return (
    <div className="relative py-2 px-3 rounded transition-colors hover:bg-surface-700/40 overflow-hidden">
      {/* Delta bar background */}
      {card.delta_vs_field !== 0 && (
        <div
          className={`absolute inset-y-0 ${positive ? "left-0" : "right-0"} ${
            positive ? "bg-emerald-500/8" : "bg-red-500/8"
          }`}
          style={{ width: `${barWidth}%` }}
        />
      )}
      <div className="relative flex items-center justify-between gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="font-mono text-xs w-7 h-6 flex items-center justify-center rounded bg-surface-700 text-slate-300 shrink-0 tabular-nums">
            {copies}
          </span>
          <Link
            href={`/${format}/cards/${slugify(card.card_name)}`}
            className="text-sm text-slate-300 hover:text-accent transition-colors truncate"
            onClick={(e) => e.stopPropagation()}
          >
            {card.card_name}
          </Link>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <span className="text-xs font-mono text-surface-400 tabular-nums w-10 text-right">
            {card.inclusion_pct.toFixed(0)}%
          </span>
          <span className="w-12 text-right">
            <DeltaBadge delta={card.delta_vs_field} />
          </span>
        </div>
      </div>
    </div>
  );
}

function CardGroup({
  title,
  colorClass,
  cards,
  format,
}: {
  title: string;
  colorClass: string;
  cards: TopPerformerCard[];
  format: string;
}) {
  if (cards.length === 0) return null;

  return (
    <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
      <div className="px-3 py-2 border-b border-surface-600 flex items-center justify-between">
        <h3 className={`text-xs font-semibold ${colorClass} uppercase tracking-wider`}>
          {title}
        </h3>
        <span className="text-[10px] font-mono text-surface-400">
          {cards.length}
        </span>
      </div>
      <div className="px-3 py-1.5 border-b border-surface-600/50 flex items-center justify-between">
        <span className="text-[10px] text-surface-500 uppercase tracking-wider">
          Copies / Card
        </span>
        <div className="flex items-center gap-3">
          <span className="text-[10px] text-surface-500 uppercase tracking-wider w-10 text-right">
            Top 4
          </span>
          <span className="text-[10px] text-surface-500 uppercase tracking-wider w-12 text-right">
            Delta
          </span>
        </div>
      </div>
      <div className="p-1.5 space-y-0.5">
        {cards.map((card) => (
          <TopCardRow key={card.card_name} card={card} format={format} />
        ))}
      </div>
    </div>
  );
}

interface Top4CardStatsProps {
  cards: TopPerformerCard[];
  sampleSize: number;
  lowSample: boolean;
  deckCount: number;
  format: string;
}

export function Top4CardStats({
  cards,
  sampleSize,
  lowSample,
  deckCount,
  format,
}: Top4CardStatsProps) {
  const [filter, setFilter] = useState<CategoryFilter>("all");

  const filtered =
    filter === "all" ? cards : cards.filter((c) => c.category === filter);

  // Sort by delta descending (biggest overperformers first)
  const sorted = [...filtered].sort(
    (a, b) => b.delta_vs_field - a.delta_vs_field,
  );

  const overperformers = sorted.filter((c) => c.delta_vs_field > 0);
  const underperformers = sorted.filter((c) => c.delta_vs_field < 0);
  const neutral = sorted.filter((c) => c.delta_vs_field === 0);

  return (
    <section>
      <div className="flex items-start justify-between gap-4 mb-1">
        <h2 className="font-display text-lg font-semibold text-slate-100">
          Top 4 Card Analysis
        </h2>
        <div className="flex gap-1 shrink-0">
          {categories.map((cat) => (
            <button
              key={cat.value}
              onClick={() => setFilter(cat.value)}
              className={`px-2 py-0.5 rounded text-xs transition-colors ${
                filter === cat.value
                  ? "bg-surface-600 text-slate-200"
                  : "text-surface-400 hover:text-slate-300"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>
      <p className="text-xs text-surface-400 mb-4">
        Inclusion rate delta for top-4 finishers ({sampleSize} decks) vs the
        full field ({deckCount} decks).
        {lowSample && (
          <span className="text-amber-400/80 ml-1">
            Low sample size -- deltas may be noisy.
          </span>
        )}
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <CardGroup
          title="Overperformers"
          colorClass="text-emerald-400/80"
          cards={overperformers}
          format={format}
        />
        <CardGroup
          title="Underperformers"
          colorClass="text-red-400/80"
          cards={underperformers}
          format={format}
        />
      </div>

      {/* Neutral cards (no delta) - collapsed */}
      {neutral.length > 0 && (
        <p className="text-xs text-surface-500 mt-3">
          {neutral.length} cards with no difference between top-4 and field.
        </p>
      )}
    </section>
  );
}
