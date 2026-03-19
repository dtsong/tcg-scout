"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import type { CardAnalysisData, CardAnalysisEntry } from "@/app/lib/types";

type CategoryFilter = "all" | "Pokemon" | "Trainer" | "Energy";
type SortField = "avg_delta" | "max_delta" | "archetype_count";

const categories: { label: string; value: CategoryFilter }[] = [
  { label: "All", value: "all" },
  { label: "Pokemon", value: "Pokemon" },
  { label: "Trainer", value: "Trainer" },
  { label: "Energy", value: "Energy" },
];

function DeltaValue({ delta }: { delta: number }) {
  if (delta === 0) return <span className="text-xs font-mono text-surface-400">0.0</span>;
  const positive = delta > 0;
  return (
    <span className={`text-xs font-mono tabular-nums ${positive ? "text-emerald-400" : "text-red-400"}`}>
      {positive ? "+" : ""}{delta.toFixed(1)}
    </span>
  );
}

function CardRow({
  card,
  format,
  expanded,
  onToggle,
}: {
  card: CardAnalysisEntry;
  format: string;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="border-b border-surface-700 last:border-0">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between gap-4 hover:bg-surface-700/40 transition-colors text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-sm text-slate-300 truncate">{card.card_name}</span>
          <span className="text-[10px] text-surface-500 uppercase">{card.category}</span>
        </div>
        <div className="flex items-center gap-6 shrink-0">
          <div className="text-right w-16">
            <DeltaValue delta={card.avg_delta} />
          </div>
          <div className="text-right w-16">
            <DeltaValue delta={card.max_delta} />
          </div>
          <span className="text-xs text-surface-400 font-mono w-8 text-right">
            {card.archetype_count}
          </span>
        </div>
      </button>
      {expanded && (
        <div className="px-4 pb-3 space-y-1">
          {card.archetypes.map((a) => (
            <div key={a.slug} className="flex items-center justify-between gap-2 py-1.5 px-3 rounded bg-surface-800">
              <Link
                href={`/${format}/archetypes/${a.slug}`}
                className="text-xs text-slate-400 hover:text-accent truncate"
              >
                {a.archetype}
              </Link>
              <div className="flex items-center gap-4 shrink-0">
                <span className="text-[10px] text-surface-500">{a.top4_inclusion_pct.toFixed(0)}% top4</span>
                <span className="text-[10px] text-surface-500">{a.field_inclusion_pct.toFixed(0)}% field</span>
                <span className="w-14 text-right"><DeltaValue delta={a.delta_vs_field} /></span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function CardAnalysisClient({
  data,
  format,
}: {
  data: CardAnalysisData;
  format: string;
}) {
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>("all");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<SortField>("avg_delta");
  const [expandedCard, setExpandedCard] = useState<string | null>(null);

  const filtered = useMemo(() => {
    let cards = data.cards;
    if (categoryFilter !== "all") {
      cards = cards.filter((c) => c.category === categoryFilter);
    }
    if (search) {
      const q = search.toLowerCase();
      cards = cards.filter(
        (c) =>
          c.card_name.toLowerCase().includes(q) ||
          c.best_archetype.toLowerCase().includes(q) ||
          c.archetypes.some((a) => a.archetype.toLowerCase().includes(q)),
      );
    }
    return [...cards].sort((a, b) => {
      if (sortBy === "archetype_count") return b.archetype_count - a.archetype_count;
      return b[sortBy] - a[sortBy];
    });
  }, [data.cards, categoryFilter, search, sortBy]);

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold text-slate-100">Card Analysis</h1>
          <p className="text-sm text-surface-400 mt-1">
            Top-4 inclusion deltas across archetypes. {filtered.length} cards shown.
          </p>
        </div>
        <div className="flex gap-1 shrink-0">
          {categories.map((cat) => (
            <button
              key={cat.value}
              onClick={() => setCategoryFilter(cat.value)}
              className={`px-2 py-0.5 rounded text-xs transition-colors ${
                categoryFilter === cat.value
                  ? "bg-surface-600 text-slate-200"
                  : "text-surface-400 hover:text-slate-300"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <input
          type="text"
          placeholder="Search cards or archetypes..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="bg-surface-700 border border-surface-600 rounded-md px-3 py-1.5 text-sm text-slate-300 placeholder:text-surface-500 focus:outline-none focus:border-surface-400 w-64"
        />
        <div className="flex gap-1 text-[10px]">
          {(["avg_delta", "max_delta", "archetype_count"] as SortField[]).map((field) => (
            <button
              key={field}
              onClick={() => setSortBy(field)}
              className={`px-2 py-1 rounded transition-colors ${
                sortBy === field ? "bg-surface-600 text-slate-200" : "text-surface-400 hover:text-slate-300"
              }`}
            >
              {field === "avg_delta" ? "Avg Delta" : field === "max_delta" ? "Max Delta" : "# Archetypes"}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
        <div className="px-4 py-2 border-b border-surface-600 flex items-center justify-between">
          <span className="text-[10px] text-surface-500 uppercase tracking-wider">Card</span>
          <div className="flex items-center gap-6">
            <span className="text-[10px] text-surface-500 uppercase tracking-wider w-16 text-right">Avg Delta</span>
            <span className="text-[10px] text-surface-500 uppercase tracking-wider w-16 text-right">Max Delta</span>
            <span className="text-[10px] text-surface-500 uppercase tracking-wider w-8 text-right">Archs</span>
          </div>
        </div>
        {filtered.length === 0 ? (
          <div className="px-4 py-8 text-center text-surface-400 text-sm">No matching cards.</div>
        ) : (
          filtered.map((card) => (
            <CardRow
              key={card.card_name}
              card={card}
              format={format}
              expanded={expandedCard === card.card_name}
              onToggle={() => setExpandedCard(expandedCard === card.card_name ? null : card.card_name)}
            />
          ))
        )}
      </div>
    </div>
  );
}
