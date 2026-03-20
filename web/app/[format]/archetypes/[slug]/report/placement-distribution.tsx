import type { PlacementBracket } from "@/app/lib/types";

export function PlacementDistribution({
  brackets,
}: {
  brackets: PlacementBracket[];
}) {
  if (brackets.length === 0) return null;
  const maxPct = Math.max(...brackets.map((b) => b.pct));

  return (
    <div className="space-y-2">
      {brackets.map((bracket) => (
        <div key={bracket.bracket} className="flex items-center gap-3">
          <span className="text-xs font-mono text-surface-300 w-16 text-right shrink-0">
            {bracket.bracket}
          </span>
          <div className="flex-1 h-6 bg-surface-700/50 rounded overflow-hidden relative">
            <div
              className="h-full bg-accent/30 rounded transition-all duration-500"
              style={{ width: `${(bracket.pct / maxPct) * 100}%` }}
            />
            <span className="absolute inset-y-0 left-2 flex items-center text-xs font-mono text-slate-300 tabular-nums">
              {bracket.count}
            </span>
          </div>
          <span className="text-xs font-mono text-surface-400 w-12 text-right tabular-nums shrink-0">
            {bracket.pct.toFixed(1)}%
          </span>
        </div>
      ))}
    </div>
  );
}
