"use client";

import { useState, useEffect } from "react";
import { SpriteRow } from "@/app/components/sprite-row";
import { StatCard } from "@/app/components/stat-card";
import { cn, formatPct } from "@/app/lib/utils";
import type {
  Optimal60Index,
  Optimal60IndexEntry,
  Optimal60Detail,
  Optimal60Card,
  Optimal60Consensus,
} from "@/app/lib/types";

// --- Consensus tier config ---

const consensusConfig: Record<
  Optimal60Consensus,
  { bg: string; text: string; label: string; cardText: string }
> = {
  core: {
    bg: "bg-amber-500/15",
    text: "text-amber-400",
    label: "core",
    cardText: "text-slate-100 font-medium",
  },
  "flex-core": {
    bg: "bg-amber-500/10",
    text: "text-amber-400/70",
    label: "flex-core",
    cardText: "text-slate-200",
  },
  flex: {
    bg: "bg-accent/10",
    text: "text-accent/70",
    label: "flex",
    cardText: "text-slate-300",
  },
  tech: {
    bg: "bg-surface-600/50",
    text: "text-surface-400",
    label: "tech",
    cardText: "text-slate-400 italic",
  },
  "cl-signal": {
    bg: "bg-teal-500/15",
    text: "text-teal-400",
    label: "CL",
    cardText: "text-teal-300 italic",
  },
};

// --- Card row with CL overlay ---

function Optimal60CardRow({ card }: { card: Optimal60Card }) {
  const config = consensusConfig[card.consensus];
  const showDelta = Math.abs(card.inclusion_delta) > 15 && card.cl_inclusion_pct > 0;

  return (
    <div className="relative py-1.5 px-3 rounded transition-colors hover:bg-surface-700/40 overflow-hidden group">
      {/* Blended inclusion background bar */}
      <div
        className={cn(
          "absolute inset-y-0 left-0",
          card.consensus === "core" || card.consensus === "flex-core"
            ? "bg-amber-500/10"
            : card.consensus === "cl-signal"
              ? "bg-teal-500/8"
              : "bg-surface-600/20",
        )}
        style={{ width: `${Math.min(card.blended_inclusion_pct, 100)}%` }}
      />
      {/* CL overlay strip at top */}
      {card.cl_inclusion_pct > 0 && (
        <div
          className="absolute top-0 left-0 h-0.5 bg-teal-400/40"
          style={{ width: `${Math.min(card.cl_inclusion_pct, 100)}%` }}
        />
      )}
      <div className="relative flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-mono text-xs w-6 h-5 flex items-center justify-center rounded bg-surface-700 text-slate-300 shrink-0 tabular-nums">
            {card.count}
          </span>
          <span className={cn("text-sm truncate", config.cardText)}>
            {card.card_name}
          </span>
        </div>
        <div className="flex items-center gap-1.5 ml-2 shrink-0">
          {showDelta && (
            <span
              className={cn(
                "text-[9px] font-mono tabular-nums px-1 py-0.5 rounded",
                card.inclusion_delta > 0
                  ? "bg-teal-500/15 text-teal-400"
                  : "bg-rose-500/15 text-rose-400",
              )}
            >
              {card.inclusion_delta > 0 ? "+" : ""}
              {card.inclusion_delta.toFixed(0)}
            </span>
          )}
          <span
            className={cn(
              "text-[10px] font-mono tabular-nums",
              card.consensus === "core" ? "text-amber-500/80" : "text-surface-400",
            )}
          >
            {card.blended_inclusion_pct.toFixed(0)}%
          </span>
          <span
            className={cn("text-[9px] px-1.5 py-0.5 rounded-full", config.bg, config.text)}
          >
            {config.label}
          </span>
        </div>
      </div>
      {/* Insight tooltip on hover */}
      {card.insight && (
        <div className="hidden group-hover:block absolute bottom-full left-0 right-0 mb-1 z-10 px-3 py-2 bg-surface-700 border border-surface-500 rounded-lg shadow-lg text-xs text-slate-300">
          {card.insight}
        </div>
      )}
    </div>
  );
}

// --- Category column ---

function CategoryColumn({
  title,
  cards,
  count,
}: {
  title: string;
  cards: Optimal60Card[];
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
          <Optimal60CardRow key={card.card_name} card={card} />
        ))}
      </div>
    </div>
  );
}

// --- Archetype selector tile ---

function formatOrdinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

function ArchetypeTile({
  entry,
  active,
  onClick,
}: {
  entry: Optimal60IndexEntry;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-2 px-3 py-2 rounded-lg border transition-all",
        active
          ? "bg-surface-600 border-surface-400 ring-1 ring-accent/30"
          : "bg-surface-800 border-surface-600 hover:border-surface-500 hover:bg-surface-700",
      )}
    >
      <SpriteRow filenames={entry.sprite_filenames ?? []} size={22} />
      <span className={cn("text-sm whitespace-nowrap", active ? "text-slate-100" : "text-slate-300")}>
        {entry.archetype}
      </span>
      <span className="text-[10px] font-mono text-surface-400 ml-0.5">
        {entry.meta_share.toFixed(1)}%
      </span>
      {entry.cl_best_finish != null && (
        <span className="text-[9px] font-mono text-teal-400 ml-0.5">
          CL {formatOrdinal(entry.cl_best_finish)}
        </span>
      )}
    </button>
  );
}

// --- Divergence panel ---

function DivergencePanel({ cards }: { cards: Optimal60Card[] }) {
  const divergent = cards
    .filter((c) => Math.abs(c.inclusion_delta) > 10 && c.cl_inclusion_pct > 0)
    .sort((a, b) => Math.abs(b.inclusion_delta) - Math.abs(a.inclusion_delta))
    .slice(0, 8);

  if (divergent.length === 0) return null;

  return (
    <section>
      <h2 className="font-display text-lg font-semibold text-slate-100 mb-1">
        CL vs Meta Divergences
      </h2>
      <p className="text-xs text-surface-400 mb-3">
        Cards where Fukuoka CL results diverge most from City League consensus.
      </p>
      <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
        <div className="grid grid-cols-[1fr_60px_60px_50px] gap-2 px-4 py-2 border-b border-surface-600 text-[10px] text-surface-400 uppercase tracking-wider font-semibold">
          <span>Card</span>
          <span className="text-right">CL %</span>
          <span className="text-right">Meta %</span>
          <span className="text-right">Delta</span>
        </div>
        {divergent.map((card) => (
          <div
            key={card.card_name}
            className="grid grid-cols-[1fr_60px_60px_50px] gap-2 px-4 py-2.5 border-b border-surface-700/50 last:border-0 hover:bg-surface-700/30 transition-colors"
          >
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-sm text-slate-300 truncate">{card.card_name}</span>
              {card.insight && (
                <span className="text-[10px] text-surface-400 truncate hidden sm:inline">
                  {card.insight}
                </span>
              )}
            </div>
            <span className="text-right text-sm font-mono tabular-nums text-teal-400">
              {card.cl_inclusion_pct.toFixed(0)}%
            </span>
            <span className="text-right text-sm font-mono tabular-nums text-slate-400">
              {card.meta_inclusion_pct.toFixed(0)}%
            </span>
            <span
              className={cn(
                "text-right text-sm font-mono tabular-nums",
                card.inclusion_delta > 0 ? "text-teal-400" : "text-rose-400",
              )}
            >
              {card.inclusion_delta > 0 ? "+" : ""}
              {card.inclusion_delta.toFixed(0)}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

// --- Main component ---

export function Optimal60Client({
  index,
  format,
}: {
  index: Optimal60Index;
  format: string;
}) {
  const [selectedSlug, setSelectedSlug] = useState(index.archetypes[0]?.slug ?? "");
  const [detail, setDetail] = useState<Optimal60Detail | null>(null);
  const [loading, setLoading] = useState(false);

  // Load archetype detail on selection change
  useEffect(() => {
    if (!selectedSlug) return;
    setLoading(true);
    fetch(`/data/${format}/optimal-60/${selectedSlug}.json`)
      .then((res) => res.json())
      .then((data: Optimal60Detail) => {
        setDetail(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [selectedSlug, format]);

  const selected = index.archetypes.find((a) => a.slug === selectedSlug);

  return (
    <div className="space-y-8">
      {/* Hero */}
      <div>
        <h1 className="font-display text-2xl font-bold text-slate-100 mb-1">
          Optimal 60
        </h1>
        <p className="text-sm text-surface-400 max-w-2xl">
          Data-backed decklists for top archetypes, blending{" "}
          <span className="text-teal-400">{index.cl_event}</span>{" "}
          ({index.cl_player_count.toLocaleString()} players) with broader City League results.
        </p>
      </div>

      {/* Format context */}
      <div className="bg-surface-800 border-l-4 border-teal-500/50 rounded-r-lg p-4">
        <p className="text-xs text-slate-400 leading-relaxed">
          {index.format_note} International tournaments (best-of-3) may favor
          slightly different card counts than the BO1 data shown here. Cards
          that reward consistency in longer sets (extra copies of key Supporters,
          counter-tech) may be underrepresented.
        </p>
      </div>

      {/* Archetype selector */}
      <div className="flex flex-wrap gap-2 pb-2">
        {index.archetypes.map((entry) => (
          <ArchetypeTile
            key={entry.slug}
            entry={entry}
            active={entry.slug === selectedSlug}
            onClick={() => setSelectedSlug(entry.slug)}
          />
        ))}
      </div>

      {/* Selected archetype stats */}
      {selected && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatCard
              label="Meta Share"
              value={formatPct(selected.meta_share)}
              tooltip="Percentage of all tournament decks that play this archetype across the Nihil Zero format"
            />
            <StatCard
              label="List Consensus"
              value={`${selected.quality_score.toFixed(0)}%`}
              tooltip="Average inclusion rate across the 60 cards. 90%+ means most players agree on the exact list. Lower scores mean more flex slots where players disagree."
            />
            <StatCard
              label="Sample Size"
              value={selected.city_league_deck_count + selected.cl_deck_count}
              tooltip={`Built from ${selected.city_league_deck_count} City League decklists${selected.cl_deck_count > 0 ? ` and ${selected.cl_deck_count} Fukuoka CL decklists (weighted 5x)` : ""}`}
            />
            {selected.cl_best_finish != null ? (
              <StatCard
                label="Fukuoka CL"
                value={formatOrdinal(selected.cl_best_finish)}
                tooltip={`Best CL finish. All CL placements: ${selected.cl_placements.map(formatOrdinal).join(", ")}`}
              />
            ) : (
              <StatCard
                label="Fukuoka CL"
                value="--"
                tooltip="No top-32 finishes at Fukuoka Champions League"
              />
            )}
          </div>
          {/* CL placements detail */}
          {selected.cl_placements.length > 0 && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-surface-400">Fukuoka CL finishes:</span>
              <div className="flex gap-1">
                {selected.cl_placements.map((p, i) => (
                  <span
                    key={i}
                    className={cn(
                      "px-1.5 py-0.5 rounded font-mono text-[11px]",
                      p <= 8
                        ? "bg-teal-500/15 text-teal-400"
                        : p <= 16
                          ? "bg-teal-500/8 text-teal-400/70"
                          : "bg-surface-700 text-surface-400",
                    )}
                  >
                    {formatOrdinal(p)}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Decklist */}
      {loading && (
        <div className="text-center py-12">
          <span className="text-sm text-surface-400">Loading decklist...</span>
        </div>
      )}

      {detail && !loading && (
        <>
          {/* Legend */}
          <div className="flex items-center gap-4 text-[10px] text-surface-400">
            <span className="flex items-center gap-1.5">
              <span className="w-8 h-0.5 bg-teal-400/40 rounded" />
              CL inclusion
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-8 h-3 bg-amber-500/10 rounded" />
              Meta consensus
            </span>
            <span className="flex items-center gap-1.5">
              <span className="px-1 py-0.5 rounded bg-teal-500/15 text-teal-400">+25</span>
              CL favored
            </span>
            <span className="flex items-center gap-1.5">
              <span className="px-1 py-0.5 rounded bg-rose-500/15 text-rose-400">-20</span>
              Meta favored
            </span>
          </div>

          {/* Three-column deck */}
          <section>
            <div className="flex items-center gap-3 mb-3">
              <span className="text-xs text-surface-400">
                {detail.total_pokemon + detail.total_trainer + detail.total_energy} cards
              </span>
              <span className="text-xs text-surface-500">|</span>
              <span className="text-xs text-surface-400">
                <span className="font-mono text-slate-300">
                  {detail.core_lock_rate.toFixed(0)}%
                </span>{" "}
                of slots are locked in across all lists
              </span>
              {detail.has_cl_data && (
                <>
                  <span className="text-xs text-surface-500">|</span>
                  <span className="text-xs text-surface-400">
                    <span className="font-mono text-slate-300">
                      {detail.innovation_index.toFixed(0)}%
                    </span>{" "}
                    of cards differ between CL and meta
                  </span>
                </>
              )}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <CategoryColumn
                title="Pokemon"
                cards={detail.cards.filter((c) => c.category === "Pokemon")}
                count={detail.total_pokemon}
              />
              <CategoryColumn
                title="Trainer"
                cards={detail.cards.filter((c) => c.category === "Trainer")}
                count={detail.total_trainer}
              />
              <CategoryColumn
                title="Energy"
                cards={detail.cards.filter((c) => c.category === "Energy")}
                count={detail.total_energy}
              />
            </div>
          </section>

          {/* Divergence panel */}
          {detail.has_cl_data && <DivergencePanel cards={detail.cards} />}

          {/* Narrative placeholder */}
          {detail.narrative?.summary && (
            <div className="bg-surface-800 border-l-4 border-amber-500 rounded-r-lg p-5">
              <p className="text-sm text-slate-300 leading-relaxed">
                {detail.narrative.summary}
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
