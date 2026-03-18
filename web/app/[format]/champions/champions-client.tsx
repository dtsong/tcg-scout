"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/app/lib/utils";
import type { CLDivision, CLPlacement } from "@/app/lib/types";

const divisionTabs = [
  { key: "juniors", label: "Juniors" },
  { key: "seniors", label: "Seniors" },
  { key: "masters", label: "Masters" },
] as const;

type DivisionKey = (typeof divisionTabs)[number]["key"];

function PlacementRow({ placement }: { placement: CLPlacement }) {
  const [expanded, setExpanded] = useState(false);

  const grouped = {
    Pokemon: placement.decklist.filter((c) => c.category === "Pokemon"),
    Trainer: placement.decklist.filter((c) => c.category === "Trainer"),
    Energy: placement.decklist.filter((c) => c.category === "Energy"),
  };

  return (
    <>
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
          {placement.region}
        </td>
      </tr>
      {expanded && placement.decklist.length > 0 && (
        <tr>
          <td colSpan={3} className="bg-surface-700/30 px-4 py-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 max-w-3xl">
              {(["Pokemon", "Trainer", "Energy"] as const).map((cat) => {
                const cards = grouped[cat];
                if (cards.length === 0) return null;
                const total = cards.reduce((s, c) => s + c.count, 0);
                return (
                  <div key={cat}>
                    <h4 className="text-xs text-surface-300 uppercase tracking-wider mb-2">
                      {cat}{" "}
                      <span className="text-surface-400">({total})</span>
                    </h4>
                    <div className="space-y-1">
                      {cards.map((card, i) => (
                        <div key={i} className="flex items-start justify-between text-sm">
                          <span className="text-slate-300">
                            {card.card_name_en || card.card_name_jp}
                            {card.card_name_en && card.card_name_en !== card.card_name_jp && (
                              <span className="text-surface-400 text-xs ml-1.5">
                                {card.card_name_jp}
                              </span>
                            )}
                          </span>
                          <span className="font-mono text-xs text-surface-300 ml-2 tabular-nums">
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
    </>
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

      {/* Placements Table */}
      <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-600 text-xs text-surface-300 uppercase tracking-wider">
                <th className="text-left px-4 py-3 w-16">#</th>
                <th className="text-left px-4 py-3">Player</th>
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
