"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import type { CardAnalysisData, CardAnalysisEntry } from "@/app/lib/types";
import { slugify, effectiveImpact, effectiveConfidence } from "@/app/lib/utils";
import { DeltaValue } from "@/app/components/delta-value";
import { InfoIcon } from "@/app/components/tooltip";
import { CardLink } from "@/app/components/card-link";

type CategoryFilter = "all" | "Pokemon" | "Trainer" | "Energy";
type SortField = "weighted_impact" | "max_delta" | "archetype_count";

const categories: { label: string; value: CategoryFilter }[] = [
  { label: "All", value: "all" },
  { label: "Pokemon", value: "Pokemon" },
  { label: "Trainer", value: "Trainer" },
  { label: "Energy", value: "Energy" },
];

const sortOptions: { label: string; value: SortField }[] = [
  { label: "Impact", value: "weighted_impact" },
  { label: "Best Edge", value: "max_delta" },
  { label: "# Archetypes", value: "archetype_count" },
];

const CONFIDENCE_LABELS = {
  card: {
    high: "High confidence (all archetypes have 10+ top-4 decks)",
    medium: "Medium confidence (smallest archetype sample: 5-9 top-4 decks)",
    low: "Limited data (at least one archetype has fewer than 5 top-4 decks)",
  },
  archetype: {
    high: "High confidence (10+ top-4 decks)",
    medium: "Medium confidence (5-9 top-4 decks)",
    low: "Limited data (fewer than 5 top-4 decks)",
  },
} as const;

function getConfidenceLevel(confidence: number): { color: string; tier: "high" | "medium" | "low" } {
  if (confidence >= 1.0) return { color: "bg-emerald-400", tier: "high" };
  if (confidence >= 0.5) return { color: "bg-amber-400/70", tier: "medium" };
  return { color: "bg-surface-500", tier: "low" };
}

function ConfidenceDot({ confidence = 1, level = "archetype" }: { confidence?: number; level?: "card" | "archetype" }) {
  const { color, tier } = getConfidenceLevel(confidence);
  const label = CONFIDENCE_LABELS[level][tier];
  return <span className={`inline-block w-2 h-2 rounded-full ${color}`} title={label} />;
}

function DeltaBar({ top4Pct, fieldPct }: { top4Pct: number; fieldPct: number }) {
  const maxPct = Math.max(top4Pct, fieldPct, 1);
  return (
    <div className="flex flex-col gap-0.5 w-20">
      <div className="flex items-center gap-1.5">
        <div className="h-1.5 rounded-full bg-teal-500/80" style={{ width: `${(top4Pct / maxPct) * 100}%`, minWidth: top4Pct > 0 ? "2px" : "0" }} />
        <span className="text-[9px] text-surface-500 tabular-nums font-mono">{top4Pct.toFixed(0)}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <div className="h-1.5 rounded-full bg-surface-500/60" style={{ width: `${(fieldPct / maxPct) * 100}%`, minWidth: fieldPct > 0 ? "2px" : "0" }} />
        <span className="text-[9px] text-surface-500 tabular-nums font-mono">{fieldPct.toFixed(0)}</span>
      </div>
    </div>
  );
}

function FeaturedCard({ card, format }: { card: CardAnalysisEntry; format: string }) {
  return (
    <Link
      href={`/${format}/cards/${slugify(card.card_name)}`}
      className="flex-shrink-0 w-40 bg-surface-800 border border-surface-600 rounded-lg p-3 hover:border-surface-400 transition-colors group"
    >
      <p className="text-sm text-slate-200 font-medium truncate group-hover:text-accent transition-colors">
        {card.card_name}
      </p>
      <p className="text-[10px] text-surface-500 uppercase mt-0.5">{card.category}</p>
      <div className="flex items-center justify-between mt-2">
        <DeltaValue delta={effectiveImpact(card)} size="lg" />
        <div className="flex items-center gap-1.5">
          <ConfidenceDot confidence={card.confidence} level="card" />
          <span className="text-[10px] text-surface-400 font-mono">{card.archetype_count} arch</span>
        </div>
      </div>
    </Link>
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
    <div className="border-b border-surface-700 last:border-0" data-testid="card-row">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between gap-4 hover:bg-surface-700/40 transition-colors text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          <CardLink name={card.card_name} format={format} className="text-sm text-slate-300 truncate" />
          <span className="text-[10px] text-surface-500 uppercase hidden sm:inline">{card.category}</span>
        </div>
        <div className="flex items-center gap-4 sm:gap-6 shrink-0">
          <div className="text-right w-14">
            <DeltaValue delta={effectiveImpact(card)} />
          </div>
          <div className="text-right w-14 hidden sm:block">
            <DeltaValue delta={card.max_delta} />
          </div>
          <div className="flex items-center gap-1.5">
            <ConfidenceDot confidence={card.confidence} level="card" />
            <span className="text-xs text-surface-400 font-mono w-6 text-right">
              {card.archetype_count}
            </span>
          </div>
        </div>
      </button>
      {expanded && (
        <div className="px-4 pb-3 space-y-1" data-testid="archetype-breakdown">
          {card.archetypes.map((a) => (
            <div key={a.slug} className="flex items-center justify-between gap-2 py-1.5 px-3 rounded bg-surface-800">
              <div className="flex items-center gap-2 min-w-0">
                <ConfidenceDot confidence={a.confidence} />
                <Link
                  href={`/${format}/archetypes/${a.slug}`}
                  className="text-xs text-slate-400 hover:text-accent truncate"
                >
                  {a.archetype}
                </Link>
              </div>
              <div className="flex items-center gap-4 shrink-0">
                <DeltaBar top4Pct={a.top4_inclusion_pct} fieldPct={a.field_inclusion_pct} />
                <span className="w-12 text-right"><DeltaValue delta={a.delta_vs_field} /></span>
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
  const [sortBy, setSortBy] = useState<SortField>("weighted_impact");
  const [expandedCard, setExpandedCard] = useState<string | null>(null);

  const featuredCards = useMemo(() => {
    return data.cards
      .filter((c) => effectiveImpact(c) > 0 && effectiveConfidence(c) >= 0.5)
      .sort((a, b) => effectiveImpact(b) - effectiveImpact(a))
      .slice(0, 8);
  }, [data.cards]);

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
      if (sortBy === "weighted_impact") return effectiveImpact(b) - effectiveImpact(a);
      return b[sortBy] - a[sortBy];
    });
  }, [data.cards, categoryFilter, search, sortBy]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="font-display text-2xl font-bold text-slate-100">Format Edge</h1>
          <p className="text-sm text-surface-400 mt-1">
            Cards that appear more in top-4 finishes than in the field, weighted by archetype tier and sample size.{" "}
            <Link href={`/${format}/guide#format-edge`} className="text-accent hover:text-accent/80 transition-colors">
              How this works &rarr;
            </Link>
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

      {/* Featured Cards Strip */}
      {featuredCards.length > 0 && (
        <div>
          <h2 className="font-display text-xs font-semibold text-surface-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            Top Impact Cards
            <InfoIcon tooltip="Cards with the highest tier-weighted edge score and at least medium data confidence. Impact is weighted so cards winning in S-tier archetypes rank higher than those in Rogue decks." />
          </h2>
          <div
            className="flex gap-3 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-surface-600 scrollbar-track-transparent"
          >
            {featuredCards.map((card) => (
              <FeaturedCard key={card.card_name} card={card} format={format} />
            ))}
          </div>
        </div>
      )}

      {/* Search + Sort Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <input
          type="text"
          placeholder="Search cards or archetypes..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="bg-surface-700 border border-surface-600 rounded-md px-3 py-1.5 text-sm text-slate-300 placeholder:text-surface-500 focus:outline-none focus:border-surface-400 w-64"
        />
        <div className="flex gap-1 text-[10px]">
          {sortOptions.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setSortBy(opt.value)}
              className={`px-2 py-1 rounded transition-colors ${
                sortBy === opt.value ? "bg-surface-600 text-slate-200" : "text-surface-400 hover:text-slate-300"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <span className="text-[10px] text-surface-500 ml-auto">{filtered.length} cards</span>
      </div>

      {/* Table */}
      <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
        <div className="px-4 py-2 border-b border-surface-600 flex items-center justify-between">
          <span className="text-[10px] text-surface-500 uppercase tracking-wider">Card</span>
          <div className="flex items-center gap-4 sm:gap-6">
            <span className="text-[10px] text-surface-500 uppercase tracking-wider w-14 text-right">Impact</span>
            <span className="text-[10px] text-surface-500 uppercase tracking-wider w-14 text-right hidden sm:block">Best Edge</span>
            <span className="text-[10px] text-surface-500 uppercase tracking-wider w-10 text-right">Archs</span>
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
