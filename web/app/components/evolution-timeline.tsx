import type { EvolutionEvent } from "@/app/lib/types";
import { TrendingUp, TrendingDown } from "lucide-react";

function formatWeek(dateStr: string): string {
  const d = new Date(dateStr);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

export function EvolutionTimeline({
  evolution,
}: {
  evolution: EvolutionEvent[];
}) {
  return (
    <section>
      <h2 className="font-display text-lg font-semibold text-slate-100 mb-1">
        List Evolution
      </h2>
      <p className="text-xs text-surface-400 mb-4">
        Week-over-week card adoption and drop events
      </p>
      <div className="space-y-3">
        {evolution.map((event) => (
          <div
            key={event.week}
            className="bg-surface-800 border border-surface-600 rounded-lg p-4"
          >
            <div className="text-xs font-mono text-surface-400 mb-2">
              Week of {formatWeek(event.week)}
            </div>
            <div className="space-y-1.5">
              {event.adopted.map((card) => (
                <div
                  key={`adopt-${card.card}`}
                  className="flex items-center gap-2 text-sm"
                >
                  <TrendingUp className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  <span className="text-slate-200">{card.card}</span>
                  <span className="text-xs font-mono text-surface-400 ml-auto">
                    {card.from_pct.toFixed(0)}% &rarr; {card.to_pct.toFixed(0)}%
                  </span>
                </div>
              ))}
              {event.dropped.map((card) => (
                <div
                  key={`drop-${card.card}`}
                  className="flex items-center gap-2 text-sm"
                >
                  <TrendingDown className="w-3.5 h-3.5 text-red-400 shrink-0" />
                  <span className="text-slate-200 opacity-60">{card.card}</span>
                  <span className="text-xs font-mono text-surface-400 ml-auto">
                    {card.from_pct.toFixed(0)}% &rarr; {card.to_pct.toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
