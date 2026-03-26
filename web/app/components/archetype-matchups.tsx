import Link from "next/link";
import { cn, slugify } from "@/app/lib/utils";
import type { ArchetypeMatchups as ArchetypeMatchupsType } from "@/app/lib/types";
import { Tooltip } from "@/app/components/tooltip";

function WinRateBar({
  winRate,
  favorable,
}: {
  winRate: number;
  favorable: boolean;
}) {
  const deviation = Math.abs(winRate - 0.5);
  const widthPct = Math.min(deviation * 200, 100);

  return (
    <div className="w-16 h-1.5 rounded-full bg-surface-700 overflow-hidden">
      <div
        className={cn(
          "h-full rounded-full",
          favorable ? "bg-emerald-500" : "bg-red-500",
        )}
        style={{ width: `${widthPct}%` }}
      />
    </div>
  );
}

function MatchupRow({
  archetype,
  winRate,
  sampleSize,
  ciLower,
  ciUpper,
  favorable,
  format,
}: {
  archetype: string;
  winRate: number;
  sampleSize: number;
  ciLower: number | null;
  ciUpper: number | null;
  favorable: boolean;
  format: string;
}) {
  const pct = Math.round(winRate * 100);
  const ciText =
    ciLower != null && ciUpper != null
      ? `${Math.round(ciLower * 100)}-${Math.round(ciUpper * 100)}%`
      : null;

  return (
    <div className="flex items-center gap-3 py-1.5">
      <Link
        href={`/${format}/archetypes/${slugify(archetype)}`}
        className="text-sm text-surface-200 hover:text-terminal truncate min-w-0 flex-1"
      >
        {archetype}
      </Link>
      <WinRateBar winRate={winRate} favorable={favorable} />
      <Tooltip
        content={
          <>
            {pct}% win rate ({sampleSize} matches)
            {ciText && <>, 95% CI: {ciText}</>}
          </>
        }
      >
        <span
          className={cn(
            "text-sm font-mono tabular-nums w-10 text-right",
            favorable ? "text-emerald-400" : "text-red-400",
          )}
        >
          {pct}%
        </span>
      </Tooltip>
      <span className="text-xs text-surface-500 w-8 text-right">{sampleSize}</span>
    </div>
  );
}

export function ArchetypeMatchups({
  matchups,
  source,
  format,
}: {
  matchups: ArchetypeMatchupsType;
  source: string;
  format: string;
}) {
  if (matchups.favorable.length === 0 && matchups.unfavorable.length === 0) {
    return null;
  }

  const sourceLabel =
    source === "labs-h2h"
      ? "Based on head-to-head match results from international Regionals, Internationals, and Worlds."
      : "Based on win-rate performance comparison within shared tournaments.";

  return (
    <section>
      <h2 className="font-display text-lg font-semibold text-slate-100 mb-1">
        Matchups
      </h2>
      <p className="text-xs text-surface-400 mb-4">{sourceLabel}</p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        {matchups.favorable.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-medium text-emerald-400 uppercase tracking-wide">
                Favorable
              </span>
              <span className="text-xs text-surface-500">Win %</span>
              <span className="text-xs text-surface-500 ml-auto">N</span>
            </div>
            {matchups.favorable.map((m) => (
              <MatchupRow
                key={m.archetype}
                archetype={m.archetype}
                winRate={m.win_rate}
                sampleSize={m.sample_size}
                ciLower={m.ci_lower}
                ciUpper={m.ci_upper}
                favorable
                format={format}
              />
            ))}
          </div>
        )}

        {matchups.unfavorable.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-medium text-red-400 uppercase tracking-wide">
                Unfavorable
              </span>
              <span className="text-xs text-surface-500">Win %</span>
              <span className="text-xs text-surface-500 ml-auto">N</span>
            </div>
            {matchups.unfavorable.map((m) => (
              <MatchupRow
                key={m.archetype}
                archetype={m.archetype}
                winRate={m.win_rate}
                sampleSize={m.sample_size}
                ciLower={m.ci_lower}
                ciUpper={m.ci_upper}
                favorable={false}
                format={format}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
