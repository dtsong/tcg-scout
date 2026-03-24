import type { ArchetypeVariant } from "@/app/lib/types";

const barColors = [
  "bg-accent",
  "bg-teal-500",
  "bg-blue-500",
  "bg-purple-500",
  "bg-amber-500",
];

export function VariantBreakdown({
  variants,
  deckCount,
}: {
  variants: ArchetypeVariant[];
  deckCount: number;
}) {
  return (
    <section>
      <h2 className="font-display text-lg font-semibold text-slate-100 mb-1">
        Variants
      </h2>
      <p className="text-xs text-surface-400 mb-3">
        Build distribution across {deckCount} decklists
      </p>

      {/* Segmented bar */}
      <div className="flex rounded-md overflow-hidden h-6 mb-3">
        {variants.map((v, i) => (
          <div
            key={v.name}
            className={`${barColors[i % barColors.length]} opacity-80 flex items-center justify-center`}
            style={{ width: `${v.pct}%` }}
            title={`${v.name}: ${v.pct}%`}
          >
            {v.pct >= 15 && (
              <span className="text-[10px] font-mono text-white font-medium truncate px-1">
                {v.pct.toFixed(0)}%
              </span>
            )}
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3">
        {variants.map((v, i) => (
          <div key={v.name} className="flex items-center gap-1.5">
            <div className={`w-2.5 h-2.5 rounded-sm ${barColors[i % barColors.length]} opacity-80`} />
            <span className="text-xs text-slate-300">{v.name}</span>
            <span className="text-[10px] font-mono text-surface-400">
              {v.deck_count} decks
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
