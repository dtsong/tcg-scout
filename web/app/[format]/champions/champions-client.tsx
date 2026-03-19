"use client";

import { Fragment, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/app/lib/utils";
import { SpriteRow } from "@/app/components/sprite-row";
import { TierBadge } from "@/app/components/tier-badge";
import type {
  CLArchetypeSummary,
  CLDivision,
  CLPlacement,
} from "@/app/lib/types";

const divisionTabs = [
  { key: "juniors", label: "Juniors" },
  { key: "seniors", label: "Seniors" },
  { key: "masters", label: "Masters" },
] as const;

type DivisionKey = (typeof divisionTabs)[number]["key"];

function PlacementRow({ placement }: { placement: CLPlacement }) {
  const [expanded, setExpanded] = useState(false);
  const [failedImages, setFailedImages] = useState<Record<number, boolean>>({});

  const grouped = {
    Pokemon: placement.decklist.filter((c) => c.category === "Pokemon"),
    Trainer: placement.decklist.filter((c) => c.category === "Trainer"),
    Energy: placement.decklist.filter((c) => c.category === "Energy"),
  };

  return (
    <Fragment>
      <tr
        className="border-b border-surface-700 hover:bg-surface-700/50 transition-colors cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="px-4 py-3 font-mono tabular-nums text-surface-300 w-16">
          {placement.standing}
        </td>
        <td className="px-4 py-3 text-slate-200">
          <div className="flex items-center gap-2">
            {expanded ? (
              <ChevronDown className="w-3.5 h-3.5 text-surface-400 shrink-0" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-surface-400 shrink-0" />
            )}
            {placement.player_name}
          </div>
        </td>
        <td className="px-4 py-3 text-sm text-surface-300 hidden sm:table-cell">
          <div className="flex items-center gap-2">
            {placement.sprite_filenames && placement.sprite_filenames.length > 0 && (
              <SpriteRow filenames={placement.sprite_filenames} size={20} />
            )}
            {placement.archetype ? (
              <span>{placement.archetype}</span>
            ) : (
              <span className="text-surface-400">-</span>
            )}
            {placement.tier && <TierBadge tier={placement.tier} className="w-5 h-5 text-[10px]" />}
          </div>
        </td>
        <td className="px-4 py-3 text-sm text-surface-300 hidden sm:table-cell">
          {placement.region}
        </td>
      </tr>
      {expanded && placement.decklist.length > 0 && (
        <tr>
          <td colSpan={4} className="bg-surface-700/30 px-4 py-4">
            <div className="space-y-6">
              {(["Pokemon", "Trainer", "Energy"] as const).map((cat) => {
                const cards = grouped[cat];
                if (cards.length === 0) return null;
                const total = cards.reduce((s, c) => s + c.count, 0);
                return (
                  <div key={cat}>
                    <h4 className="text-xs text-surface-300 uppercase tracking-wider mb-3">
                      {cat}{" "}
                      <span className="text-surface-400">({total})</span>
                    </h4>
                    <div className="grid grid-cols-4 sm:grid-cols-6 lg:grid-cols-8 gap-3">
                      {cards.map((card, i) => (
                        <div key={i} className="flex flex-col items-center text-center">
                          {card.image_url && !failedImages[i] ? (
                            <img
                              src={card.image_url}
                              alt={card.card_name_en || card.card_name_jp}
                              className="w-[72px] h-[100px] object-cover rounded"
                              onError={() => setFailedImages((prev) => ({ ...prev, [i]: true }))}
                            />
                          ) : (
                            <div className="w-[72px] h-[100px] rounded bg-surface-600 border border-surface-500 flex items-center justify-center p-1">
                              <span className="text-[10px] text-surface-300 leading-tight text-center break-words">
                                {card.card_name_en || card.card_name_jp}
                              </span>
                            </div>
                          )}
                          <span className="text-[10px] text-slate-300 mt-1 leading-tight line-clamp-2">
                            {card.card_name_en || card.card_name_jp}
                          </span>
                          <span className="font-mono text-[10px] text-surface-400">
                            x{card.count}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </td>
        </tr>
      )}
    </Fragment>
  );
}

function ArchetypeSummaryBar({
  summary,
}: {
  summary: CLArchetypeSummary[];
}) {
  if (!summary || summary.length === 0) return null;

  return (
    <div className="bg-surface-800 border border-surface-600 rounded-lg px-4 py-3">
      <h3 className="text-xs text-surface-300 uppercase tracking-wider mb-2">
        Archetype Distribution
      </h3>
      <div className="flex flex-wrap gap-x-4 gap-y-2">
        {summary.map((entry) => (
          <div
            key={entry.archetype}
            className="flex items-center gap-1.5 text-sm text-slate-200"
          >
            {entry.sprite_filenames && entry.sprite_filenames.length > 0 && (
              <SpriteRow filenames={entry.sprite_filenames} size={20} />
            )}
            <span>{entry.archetype}</span>
            <span className="text-surface-400 text-xs">x{entry.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ChampionsClient({
  divisions,
}: {
  divisions: Record<DivisionKey, CLDivision>;
}) {
  const [activeDiv, setActiveDiv] = useState<DivisionKey>("masters");
  const division = divisions[activeDiv];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-bold text-slate-100">
          Champions League
        </h1>
        <p className="text-sm text-surface-300 mt-1">
          {division.event_name}, {division.date}
        </p>
      </div>

      {/* Division Tabs */}
      <div className="flex items-center gap-1 border-b border-surface-600">
        {divisionTabs.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveDiv(key)}
            className={cn(
              "px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px",
              activeDiv === key
                ? "border-accent text-accent"
                : "border-transparent text-surface-300 hover:text-slate-200",
            )}
          >
            {label}
            <span className="ml-1.5 text-xs text-surface-400">
              ({divisions[key].placements.length})
            </span>
          </button>
        ))}
      </div>

      {/* Archetype Summary Bar */}
      {division.archetype_summary && (
        <ArchetypeSummaryBar summary={division.archetype_summary} />
      )}

      {/* Placements Table */}
      <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-600 text-xs text-surface-300 uppercase tracking-wider">
                <th className="text-left px-4 py-3 w-16">#</th>
                <th className="text-left px-4 py-3">Player</th>
                <th className="text-left px-4 py-3 hidden sm:table-cell">Archetype</th>
                <th className="text-left px-4 py-3 hidden sm:table-cell">Region</th>
              </tr>
            </thead>
            <tbody>
              {division.placements.map((p) => (
                <PlacementRow key={`${p.standing}-${p.player_name}`} placement={p} />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
