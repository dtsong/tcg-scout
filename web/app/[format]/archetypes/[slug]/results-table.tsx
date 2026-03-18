"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { formatPlacement } from "@/app/lib/utils";
import type { ArchetypeResult } from "@/app/lib/types";

export function ResultsTable({ results }: { results: ArchetypeResult[] }) {
  const [expanded, setExpanded] = useState(false);

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
        <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden mt-4">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-600 text-xs text-surface-300 uppercase tracking-wider">
                  <th className="text-left px-4 py-3">Date</th>
                  <th className="text-left px-4 py-3">City League</th>
                  <th className="text-right px-4 py-3">Standing</th>
                  <th className="text-left px-4 py-3 hidden sm:table-cell">Player</th>
                </tr>
              </thead>
              <tbody>
                {results.map((result) => (
                  <tr
                    key={`${result.date}-${result.standing}-${result.player_name}`}
                    className="border-b border-surface-700 hover:bg-surface-700/50 transition-colors"
                  >
                    <td className="px-4 py-3 font-mono text-xs text-surface-300">
                      {result.date}
                    </td>
                    <td className="px-4 py-3 text-slate-300 text-sm">
                      {result.tournament_name}
                    </td>
                    <td className="px-4 py-3 text-right font-mono tabular-nums">
                      {formatPlacement(result.standing)}
                    </td>
                    <td className="px-4 py-3 text-sm text-surface-300 hidden sm:table-cell">
                      {result.player_name}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
