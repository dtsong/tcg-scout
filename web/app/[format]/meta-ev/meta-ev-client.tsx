"use client";

import { useState, useMemo } from "react";
import type { ArchetypeSummary, MatchupMatrixData } from "@/app/lib/types";

interface MetaEvClientProps {
  format: string;
  archetypes: ArchetypeSummary[];
  matchups: MatchupMatrixData;
}

interface MatchupBreakdown {
  opponent: string;
  metaShare: number;
  winRate: number | null;
  sampleSize: number;
  contribution: number | null;
}

export function MetaEvClient({
  archetypes,
  matchups,
}: MetaEvClientProps) {
  const [selectedDeck, setSelectedDeck] = useState<string>("");

  // Build archetype index maps
  const archetypeMap = useMemo(() => {
    const map = new Map<string, ArchetypeSummary>();
    for (const a of archetypes) {
      map.set(a.archetype, a);
    }
    return map;
  }, [archetypes]);

  const matchupIndex = useMemo(() => {
    const map = new Map<string, number>();
    matchups.archetypes.forEach((name, i) => map.set(name, i));
    return map;
  }, [matchups]);

  // Compute EV breakdown for selected deck
  const breakdown = useMemo<MatchupBreakdown[]>(() => {
    if (!selectedDeck) return [];
    const myIdx = matchupIndex.get(selectedDeck);
    if (myIdx === undefined) return [];

    const results: MatchupBreakdown[] = [];
    for (const arch of archetypes) {
      if (arch.archetype === selectedDeck) continue;
      const oppIdx = matchupIndex.get(arch.archetype);
      const winRate =
        oppIdx !== undefined ? matchups.matrix[myIdx][oppIdx] : null;
      const sampleSize =
        oppIdx !== undefined ? matchups.sample_sizes[myIdx][oppIdx] : 0;

      results.push({
        opponent: arch.archetype,
        metaShare: arch.meta_share,
        winRate,
        sampleSize,
        contribution:
          winRate !== null ? (winRate / 100) * arch.meta_share : null,
      });
    }

    return results.sort((a, b) => b.metaShare - a.metaShare);
  }, [selectedDeck, archetypes, matchupIndex, matchups]);

  // Overall EV
  const overallEv = useMemo(() => {
    if (breakdown.length === 0) return null;
    let totalWeightedWr = 0;
    let totalShareCovered = 0;

    for (const row of breakdown) {
      if (row.winRate !== null) {
        totalWeightedWr += (row.winRate / 100) * row.metaShare;
        totalShareCovered += row.metaShare;
      }
    }

    if (totalShareCovered === 0) return null;
    // Normalize to the share we have data for
    return (totalWeightedWr / totalShareCovered) * 100;
  }, [breakdown]);

  // Tier-filtered list for the selector (only show meaningful archetypes)
  const selectableDecks = useMemo(
    () =>
      matchups.archetypes.filter((name) => {
        const arch = archetypeMap.get(name);
        return arch && arch.meta_share >= 1.0;
      }),
    [matchups.archetypes, archetypeMap],
  );

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Meta EV Calculator</h1>
        <p className="mt-1 text-sm text-surface-300">
          Select a deck to see its expected win rate against the current meta,
          weighted by each opponent&apos;s meta share.
        </p>
      </div>

      {/* Deck Selector */}
      <div>
        <label
          htmlFor="deck-select"
          className="block text-sm font-medium text-surface-300 mb-2"
        >
          Your deck
        </label>
        <select
          id="deck-select"
          value={selectedDeck}
          onChange={(e) => setSelectedDeck(e.target.value)}
          className="w-full max-w-md rounded-lg border border-surface-600 bg-surface-800 px-4 py-2.5 text-white focus:border-accent focus:outline-none"
        >
          <option value="">Select an archetype...</option>
          {selectableDecks.map((name) => {
            const arch = archetypeMap.get(name);
            const tier = arch?.tier ?? "";
            return (
              <option key={name} value={name}>
                {name} ({tier} - {arch?.meta_share.toFixed(1)}%)
              </option>
            );
          })}
        </select>
      </div>

      {/* Overall EV */}
      {selectedDeck && overallEv !== null && (
        <div className="rounded-lg border border-surface-600 bg-surface-800/60 p-6">
          <div className="flex items-center gap-6">
            <div>
              <p className="text-sm text-surface-400">Expected Win Rate</p>
              <p
                className={`text-4xl font-bold ${overallEv >= 55 ? "text-green-400" : overallEv >= 50 ? "text-accent" : overallEv >= 45 ? "text-yellow-400" : "text-red-400"}`}
              >
                {overallEv.toFixed(1)}%
              </p>
            </div>
            <div className="text-sm text-surface-400">
              <p>
                Against{" "}
                {breakdown
                  .filter((b) => b.winRate !== null)
                  .reduce((s, b) => s + b.metaShare, 0)
                  .toFixed(1)}
                % of the meta (
                {breakdown.filter((b) => b.winRate !== null).length} matchups
                with data)
              </p>
              {matchups.source && (
                <p className="mt-1 text-xs text-surface-500">
                  Data source: {matchups.source}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {selectedDeck && overallEv === null && (
        <div className="rounded-lg border border-surface-600 bg-surface-800/60 p-6 text-center text-surface-400">
          No matchup data available for {selectedDeck}.
        </div>
      )}

      {/* Matchup Breakdown Table */}
      {selectedDeck && breakdown.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-white mb-4">
            Matchup Breakdown
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-600 text-surface-400 text-left">
                  <th className="py-2 pr-3 font-medium">Opponent</th>
                  <th className="py-2 pr-3 font-medium text-right">
                    Meta Share
                  </th>
                  <th className="py-2 pr-3 font-medium text-right">
                    Win Rate
                  </th>
                  <th className="py-2 pr-3 font-medium text-right">Samples</th>
                  <th className="py-2 font-medium text-right">
                    EV Contribution
                  </th>
                </tr>
              </thead>
              <tbody>
                {breakdown.map((row) => (
                  <tr
                    key={row.opponent}
                    className="border-b border-surface-700/50 hover:bg-surface-700/30"
                  >
                    <td className="py-2 pr-3 text-white">{row.opponent}</td>
                    <td className="py-2 pr-3 text-right text-surface-300">
                      {row.metaShare.toFixed(1)}%
                    </td>
                    <td className="py-2 pr-3 text-right">
                      {row.winRate !== null ? (
                        <span
                          className={
                            row.winRate >= 55
                              ? "text-green-400"
                              : row.winRate >= 50
                                ? "text-surface-200"
                                : row.winRate >= 45
                                  ? "text-yellow-400"
                                  : "text-red-400"
                          }
                        >
                          {row.winRate.toFixed(1)}%
                        </span>
                      ) : (
                        <span className="text-surface-500">--</span>
                      )}
                    </td>
                    <td className="py-2 pr-3 text-right text-surface-500">
                      {row.sampleSize > 0 ? row.sampleSize : "--"}
                    </td>
                    <td className="py-2 text-right">
                      {row.contribution !== null ? (
                        <span
                          className={
                            row.contribution > 0
                              ? "text-surface-300"
                              : "text-surface-500"
                          }
                        >
                          {row.contribution.toFixed(2)}
                        </span>
                      ) : (
                        <span className="text-surface-500">--</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
