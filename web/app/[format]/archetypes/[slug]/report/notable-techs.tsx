import type { NotableTech } from "@/app/lib/types";
import { CardLink } from "@/app/components/card-link";

const EVENT_STYLES: Record<string, { bg: string; text: string; border: string; label: string }> = {
  appeared: { bg: "bg-emerald-500/15", text: "text-emerald-400", border: "border-emerald-400", label: "New" },
  surged: { bg: "bg-amber-500/15", text: "text-amber-400", border: "border-amber-400", label: "Surged" },
  declined: { bg: "bg-red-500/15", text: "text-red-400", border: "border-red-400", label: "Declined" },
  disappeared: { bg: "bg-surface-600/50", text: "text-surface-400", border: "border-surface-400", label: "Dropped" },
};

export function NotableTechs({ techs, format }: { techs: NotableTech[]; format: string }) {
  if (techs.length === 0) return null;

  return (
    <div className="space-y-0">
      {techs.map((tech, i) => {
        const style = EVENT_STYLES[tech.event] ?? {
          bg: "bg-surface-600/50",
          text: "text-surface-400",
          border: "border-surface-400",
          label: tech.event,
        };
        const weekDate = new Date(tech.week);
        const weekLabel = `${weekDate.getMonth() + 1}/${weekDate.getDate()}`;

        return (
          <div key={`${tech.card_name}-${i}`} className="flex items-start gap-3 py-3">
            {/* Timeline dot + line */}
            <div className="flex flex-col items-center pt-0.5">
              <div className={`w-2.5 h-2.5 rounded-full ${style.bg} border-2 ${style.border}`} />
              {i < techs.length - 1 && (
                <div className="w-px flex-1 bg-surface-600 mt-1" />
              )}
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0 pb-2">
              <div className="flex items-center gap-2 flex-wrap">
                <CardLink name={tech.card_name} format={format} className="text-sm font-medium text-slate-200 hover:text-accent transition-colors" />
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${style.bg} ${style.text}`}>
                  {style.label}
                </span>
              </div>
              <p className="text-xs text-surface-400 mt-0.5">
                {tech.from_pct.toFixed(0)}% to {tech.to_pct.toFixed(0)}% &middot; Week of {weekLabel}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
