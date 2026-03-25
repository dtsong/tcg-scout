"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, ChevronUp } from "lucide-react";
import { formatPlacement } from "@/app/lib/utils";
import type { ArchetypeResult, DecklistCard } from "@/app/lib/types";
import { CopyDecklistButton } from "@/app/components/copy-decklist-button";
import { CardLink } from "@/app/components/card-link";

function DecklistView({ decklist }: { decklist: DecklistCard[] }) {
  const grouped: Record<string, DecklistCard[]> = {};
  for (const card of decklist) {
    const cat = card.category ?? "Other";
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(card);
  }

  const categoryOrder = ["Pokemon", "Trainer", "Energy", "Other"];
  const sortedCategories = categoryOrder.filter((c) => grouped[c]);

  return (
    <div className="px-4 py-3">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {sortedCategories.map((category) => (
          <div key={category}>
            <h4 className="text-xs font-semibold text-surface-400 uppercase tracking-wider mb-2">
              {category}
            </h4>
            <ul className="space-y-0.5">
              {grouped[category].map((card) => (
                <li
                  key={card.card_name}
                  className="flex items-baseline justify-between text-sm"
                >
                  <CardLink name={card.card_name} className="text-surface-200 truncate mr-2" />
                  <span className="text-surface-400 font-mono tabular-nums shrink-0">
                    x{card.count}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="mt-3">
        <CopyDecklistButton cards={decklist} compact />
      </div>
    </div>
  );
}

export function ResultsTable({ results }: { results: ArchetypeResult[] }) {
  const [expanded, setExpanded] = useState(false);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const toggleRow = (key: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  return (
    <section>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full text-left group"
      >
        <h2 className="font-display text-lg font-semibold text-slate-100">
          Results
          <span className="text-sm font-normal text-surface-300 ml-2">
            {results.length} placements
          </span>
        </h2>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-surface-400 group-hover:text-slate-300 transition-colors" />
        ) : (
          <ChevronDown className="w-4 h-4 text-surface-400 group-hover:text-slate-300 transition-colors" />
        )}
      </button>

      {expanded && (
        <div className="bg-surface-800 border border-surface-600 rounded-md overflow-hidden mt-4">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-600 text-xs text-surface-300 uppercase tracking-wider">
                  <th className="w-8 px-2 py-3" />
                  <th className="text-left px-4 py-3">Date</th>
                  <th className="text-left px-4 py-3">City League</th>
                  <th className="text-right px-4 py-3">Standing</th>
                  <th className="text-left px-4 py-3 hidden sm:table-cell">Player</th>
                </tr>
              </thead>
              <tbody>
                {results.map((result) => {
                  const rowKey = `${result.date}-${result.standing}-${result.player_name}`;
                  const hasDecklist = !!result.decklist && result.decklist.length > 0;
                  const isRowExpanded = expandedRows.has(rowKey);

                  return (
                    <>
                      <tr
                        key={rowKey}
                        onClick={() => hasDecklist && toggleRow(rowKey)}
                        className={`border-b border-surface-700 transition-colors ${
                          hasDecklist
                            ? "cursor-pointer hover:bg-surface-700/50"
                            : "hover:bg-surface-700/50"
                        }`}
                      >
                        <td className="px-2 py-3 text-center">
                          {hasDecklist && (
                            isRowExpanded ? (
                              <ChevronDown className="w-4 h-4 text-surface-400 inline-block" />
                            ) : (
                              <ChevronRight className="w-4 h-4 text-surface-400 inline-block" />
                            )
                          )}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-surface-300">
                          {result.date}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {result.tournament_url ? (
                            <a
                              href={result.tournament_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-accent hover:text-accent/80"
                              onClick={(e) => e.stopPropagation()}
                            >
                              {result.tournament_name}
                            </a>
                          ) : (
                            <span className="text-slate-300">{result.tournament_name}</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right font-mono tabular-nums">
                          {formatPlacement(result.standing)}
                        </td>
                        <td className="px-4 py-3 text-sm text-surface-300 hidden sm:table-cell">
                          {result.player_name}
                        </td>
                      </tr>
                      {isRowExpanded && hasDecklist && (
                        <tr key={`${rowKey}-decklist`} className="border-b border-surface-700">
                          <td colSpan={5} className="bg-surface-900/50">
                            <DecklistView decklist={result.decklist!} />
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
