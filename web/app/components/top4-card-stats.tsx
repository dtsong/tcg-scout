"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { ChevronDown, ExternalLink } from "lucide-react";
import type { TopPerformerCard, CardDecklistData, CardDecklistResult } from "@/app/lib/types";
import { slugify } from "@/app/lib/utils";
import { CardLink } from "@/app/components/card-link";

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

/** Group results by archetype for display. */
function groupByArchetype(results: CardDecklistResult[]) {
  const groups: Record<string, CardDecklistResult[]> = {};
  for (const r of results) {
    if (!groups[r.archetype]) groups[r.archetype] = [];
    groups[r.archetype].push(r);
  }
  return Object.entries(groups).sort((a, b) => b[1].length - a[1].length);
}

function DecklistPanel({
  data,
  format,
}: {
  data: CardDecklistData;
  format: string;
}) {
  const grouped = groupByArchetype(data.top4_results);
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? grouped : grouped.slice(0, 3);

  return (
    <div className="mt-1 mb-2 mx-1 p-3 bg-surface-900/60 border border-surface-600/50 rounded-md space-y-3">
      <p className="text-xs text-surface-400">
        {data.top4_results.length} top-4 placements across {grouped.length} archetypes
      </p>
      {visible.map(([archetype, results]) => (
        <div key={archetype}>
          <div className="flex items-center gap-2 mb-1.5">
            <Link
              href={`/${format}/archetypes/${results[0].archetype_slug}`}
              className="text-xs font-semibold text-slate-300 hover:text-accent transition-colors"
            >
              {archetype}
            </Link>
            <span className="text-[10px] font-mono text-surface-500">
              {results.length}
            </span>
          </div>
          <div className="space-y-0.5">
            {results.slice(0, 5).map((r, i) => (
              <div
                key={`${r.date}-${r.standing}-${i}`}
                className="flex items-center justify-between gap-2 px-2 py-1 text-xs rounded hover:bg-surface-700/30"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-mono text-surface-400 w-5 shrink-0 text-right">
                    #{r.standing}
                  </span>
                  <span className="text-slate-400 truncate">
                    {r.tournament_name}
                  </span>
                  <span className="text-surface-500 shrink-0">{r.date}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="font-mono text-surface-400">
                    {r.copies}x
                  </span>
                  {r.decklist_url && (
                    <a
                      href={r.decklist_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent/70 hover:text-accent transition-colors"
                      onClick={(e) => e.stopPropagation()}
                      title="View decklist on Limitless"
                    >
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              </div>
            ))}
            {results.length > 5 && (
              <p className="text-[10px] text-surface-500 px-2">
                +{results.length - 5} more
              </p>
            )}
          </div>
        </div>
      ))}
      {!showAll && grouped.length > 3 && (
        <button
          onClick={() => setShowAll(true)}
          className="text-xs text-accent/70 hover:text-accent transition-colors"
        >
          Show {grouped.length - 3} more archetypes
        </button>
      )}
    </div>
  );
}

function TopCardRow({
  card,
  format,
  expanded,
  onToggle,
  decklistData,
  loading,
}: {
  card: TopPerformerCard;
  format: string;
  expanded: boolean;
  onToggle: () => void;
  decklistData: CardDecklistData | null;
  loading: boolean;
}) {
  const copies =
    card.avg_copies % 1 === 0
      ? card.avg_copies.toString()
      : card.avg_copies.toFixed(1);
  const absDelta = Math.abs(card.delta_vs_field);
  const barWidth = Math.min(absDelta * 3, 100);
  const positive = card.delta_vs_field > 0;

  return (
    <div>
      <button
        onClick={onToggle}
        aria-expanded={expanded}
        className="relative w-full py-2 px-3 rounded transition-colors hover:bg-surface-700/40 overflow-hidden text-left"
      >
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
            <ChevronDown
              className={`w-3 h-3 text-surface-500 shrink-0 transition-transform ${
                expanded ? "rotate-0" : "-rotate-90"
              }`}
            />
            <span className="font-mono text-xs w-7 h-6 flex items-center justify-center rounded bg-surface-700 text-slate-300 shrink-0 tabular-nums">
              {copies}
            </span>
            <CardLink name={card.card_name} className="text-sm text-slate-300 truncate" />
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
      </button>
      {expanded && (
        loading ? (
          <div className="mt-1 mb-2 mx-1 p-3 text-xs text-surface-400">
            Loading decklists...
          </div>
        ) : decklistData && decklistData.top4_results.length > 0 ? (
          <DecklistPanel data={decklistData} format={format} />
        ) : (
          <div className="mt-1 mb-2 mx-1 p-3 text-xs text-surface-500">
            No decklist data available for this card.
          </div>
        )
      )}
    </div>
  );
}

function CardGroup({
  title,
  colorClass,
  cards,
  format,
  expandedCard,
  onToggleCard,
  decklistCache,
  loadingCard,
}: {
  title: string;
  colorClass: string;
  cards: TopPerformerCard[];
  format: string;
  expandedCard: string | null;
  onToggleCard: (cardName: string) => void;
  decklistCache: Record<string, CardDecklistData>;
  loadingCard: string | null;
}) {
  if (cards.length === 0) return null;

  return (
    <div className="bg-surface-800 border border-surface-600 rounded-md overflow-hidden">
      <div className="px-3 py-2 border-b border-surface-600 flex items-center justify-between">
        <h3 className={`text-xs font-semibold ${colorClass} uppercase tracking-wider`}>
          {title}
        </h3>
        <span className="text-[10px] font-mono text-surface-400">
          {cards.length}
        </span>
      </div>
      <div className="px-3 py-1.5 border-b border-surface-600/50 flex items-center justify-between">
        <span className="text-[10px] text-surface-500 uppercase tracking-wider pl-5">
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
          <TopCardRow
            key={card.card_name}
            card={card}
            format={format}
            expanded={expandedCard === card.card_name}
            onToggle={() => onToggleCard(card.card_name)}
            decklistData={decklistCache[card.card_name] ?? null}
            loading={loadingCard === card.card_name}
          />
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
  const [expandedCard, setExpandedCard] = useState<string | null>(null);
  const [decklistCache, setDecklistCache] = useState<Record<string, CardDecklistData>>({});
  const [loadingCard, setLoadingCard] = useState<string | null>(null);

  const handleToggleCard = useCallback(
    async (cardName: string) => {
      if (expandedCard === cardName) {
        setExpandedCard(null);
        return;
      }

      setExpandedCard(cardName);

      // Fetch if not already cached
      if (!decklistCache[cardName]) {
        setLoadingCard(cardName);
        try {
          const slug = slugify(cardName);
          const res = await fetch(`/data/${format}/card-decklists/${slug}.json`);
          if (res.ok) {
            const data: CardDecklistData = await res.json();
            setDecklistCache((prev) => ({ ...prev, [cardName]: data }));
          } else if (res.status === 404) {
            // No data file for this card -- cache empty result
            setDecklistCache((prev) => ({
              ...prev,
              [cardName]: { card_name: cardName, top4_results: [] },
            }));
          }
          // Other HTTP errors (500, etc.) -- don't cache, allow retry
        } catch (err) {
          console.error(`Failed to fetch decklist data for "${cardName}":`, err);
          // Don't cache on network errors -- allow retry on next click
        } finally {
          setLoadingCard(null);
        }
      }
    },
    [expandedCard, decklistCache, format],
  );

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
        full field ({deckCount} decks). Click a card to see top-4 decklists.
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
          expandedCard={expandedCard}
          onToggleCard={handleToggleCard}
          decklistCache={decklistCache}
          loadingCard={loadingCard}
        />
        <CardGroup
          title="Underperformers"
          colorClass="text-red-400/80"
          cards={underperformers}
          format={format}
          expandedCard={expandedCard}
          onToggleCard={handleToggleCard}
          decklistCache={decklistCache}
          loadingCard={loadingCard}
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
