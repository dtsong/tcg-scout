import Link from "next/link";
import { Crosshair, ChevronRight } from "lucide-react";
import { getFormats } from "@/app/lib/data";

const FORMAT_STYLES: Record<string, { accent: string; glow: string; badge: string }> = {
  "nihil-zero": {
    accent: "text-amber-400",
    glow: "hover:border-amber-500/40 hover:shadow-[0_0_24px_-4px_rgba(245,158,11,0.15)]",
    badge: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  },
  "ninja-spinner": {
    accent: "text-teal-400",
    glow: "hover:border-teal-500/40 hover:shadow-[0_0_24px_-4px_rgba(20,184,166,0.15)]",
    badge: "bg-teal-500/15 text-teal-400 border-teal-500/30",
  },
};

const DEFAULT_STYLE = {
  accent: "text-accent",
  glow: "hover:border-surface-400",
  badge: "bg-surface-700 text-surface-300 border-surface-600",
};

export default function FormatSelectorPage() {
  const formats = getFormats();

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <div className="border-b border-surface-600 bg-surface-800/80">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center">
          <span className="flex items-center gap-2 text-accent font-display font-bold text-lg">
            <Crosshair className="w-5 h-5" />
            Scout
          </span>
        </div>
      </div>

      {/* Main */}
      <div className="flex-1 flex items-center justify-center px-4 py-16">
        <div className="w-full max-w-3xl">
          <div className="text-center mb-12">
            <h1 className="font-display text-4xl sm:text-5xl font-bold text-slate-100 tracking-tight">
              Choose a Format
            </h1>
            <p className="mt-3 text-surface-300 max-w-lg mx-auto">
              JP rotation meta intelligence. Pick a format to explore tournament results, tier lists, and trends.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {formats.map((fmt) => {
              const style = FORMAT_STYLES[fmt.slug] || DEFAULT_STYLE;
              const isActive = fmt.status === "active";

              return (
                <Link
                  key={fmt.slug}
                  href={isActive ? `/${fmt.slug}` : "#"}
                  aria-disabled={!isActive}
                  className={`group relative bg-surface-800 border border-surface-600 rounded-xl p-6 transition-all duration-200 ${
                    isActive
                      ? `${style.glow} cursor-pointer`
                      : "opacity-60 cursor-default"
                  }`}
                >
                  {/* Status badge */}
                  <div className="flex items-center justify-between mb-4">
                    <span
                      className={`text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full border ${style.badge}`}
                    >
                      {isActive ? "Active" : "Coming Soon"}
                    </span>
                    {isActive && (
                      <ChevronRight className="w-4 h-4 text-surface-500 group-hover:text-surface-300 transition-colors" />
                    )}
                  </div>

                  {/* Name */}
                  <h2 className={`font-display text-2xl font-bold ${style.accent}`}>
                    {fmt.name}
                  </h2>
                  <p className="text-sm text-surface-300 mt-0.5">
                    {fmt.name_en}
                  </p>

                  {/* Description */}
                  <p className="text-xs text-surface-400 mt-3 leading-relaxed">
                    {fmt.description}
                  </p>

                  {/* Stats */}
                  {isActive && fmt.tournament_count && fmt.tournament_count > 0 ? (
                    <div className="flex gap-6 mt-5 pt-4 border-t border-surface-700">
                      <div>
                        <span className="font-mono text-lg font-medium text-slate-200 tabular-nums">
                          {fmt.tournament_count?.toLocaleString()}
                        </span>
                        <p className="text-[10px] text-surface-400 uppercase tracking-wider mt-0.5">
                          Tournaments
                        </p>
                      </div>
                      <div>
                        <span className="font-mono text-lg font-medium text-slate-200 tabular-nums">
                          {fmt.deck_count?.toLocaleString()}
                        </span>
                        <p className="text-[10px] text-surface-400 uppercase tracking-wider mt-0.5">
                          Decks
                        </p>
                      </div>
                    </div>
                  ) : !isActive ? (
                    <div className="mt-5 pt-4 border-t border-surface-700">
                      <p className="text-xs text-surface-400">
                        First results expected after {fmt.dataset_start}
                      </p>
                    </div>
                  ) : null}
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
