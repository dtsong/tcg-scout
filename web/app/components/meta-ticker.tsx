"use client";

import { useCountUp } from "@/app/hooks/use-count-up";

interface MetaTickerProps {
  formatName: string;
  tournamentCount: number;
  deckCount: number;
  generatedAt: string;
  rotationDate?: string;
  rotationDays?: number;
}

function hoursAgo(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime();
  const hours = Math.floor(diff / (1000 * 60 * 60));
  if (hours < 1) return "<1h ago";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function MetaTicker({
  formatName,
  tournamentCount,
  deckCount,
  generatedAt,
  rotationDays,
}: MetaTickerProps) {
  const animatedTournaments = useCountUp(tournamentCount);
  const animatedDecks = useCountUp(deckCount);

  return (
    <div className="w-full bg-surface-850 border-b border-surface-700">
      <div className="flex items-center justify-center gap-4 sm:gap-6 px-4 py-1.5 font-mono text-[11px] tracking-wide text-surface-400 overflow-x-auto whitespace-nowrap">
        <span className="font-semibold text-surface-300 uppercase">
          {formatName}
        </span>

        <span className="text-surface-600">|</span>

        <span>
          <span className="tabular-nums text-surface-300">
            {animatedTournaments.toLocaleString()}
          </span>{" "}
          tournaments
        </span>

        <span className="text-surface-600">|</span>

        <span>
          <span className="tabular-nums text-surface-300">
            {animatedDecks.toLocaleString()}
          </span>{" "}
          decks
        </span>

        <span className="text-surface-600">|</span>

        <span className="flex items-center gap-1.5">
          <span
            className="inline-block w-1.5 h-1.5 rounded-full bg-terminal animate-pulse-dot"
            aria-hidden="true"
          />
          <span>Updated {hoursAgo(generatedAt)}</span>
        </span>

        {rotationDays != null && (
          <>
            <span className="text-surface-600 hidden sm:inline">|</span>
            <span className="hidden sm:inline">
              {rotationDays > 0 ? (
                <>
                  Rotation:{" "}
                  <span className="tabular-nums text-surface-300">
                    {rotationDays}d
                  </span>
                </>
              ) : (
                <span className="text-terminal">Live</span>
              )}
            </span>
          </>
        )}
      </div>
    </div>
  );
}
