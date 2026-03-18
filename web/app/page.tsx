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
          {/* Professor Oak Welcome */}
          <div className="flex flex-col items-center mb-12">
            <div className="relative mb-4">
              {/* Ambient glow */}
              <div
                className="absolute inset-0 rounded-full blur-2xl opacity-30"
                style={{ background: "radial-gradient(circle, #f59e0b 0%, transparent 70%)" }}
              />
              {/* Platform ellipse */}
              <div
                className="absolute bottom-0 left-1/2 -translate-x-1/2 w-28 h-6 rounded-full opacity-20 blur-sm"
                style={{ background: "radial-gradient(ellipse, #f59e0b 0%, transparent 70%)" }}
              />
              <img
                src="/images/professor-oak.png"
                alt="Professor Oak"
                width={128}
                height={128}
                className="relative"
                style={{ imageRendering: "pixelated" }}
              />
            </div>
            <div className="relative bg-surface-800 border-2 border-surface-500 rounded-xl px-6 py-4 max-w-md w-full" style={{ fontFamily: "var(--font-pokemon), monospace" }}>
              <div className="absolute -top-2 left-1/2 -translate-x-1/2 w-3 h-3 bg-surface-800 border-l-2 border-t-2 border-surface-500 rotate-45" />
              <p className="text-[11px] text-slate-200 leading-relaxed">
                Welcome to the world of competitive Pokemon TCG!
              </p>
              <p className="text-[11px] text-slate-200 leading-relaxed mt-2">
                I&apos;m here to help you explore Japan&apos;s City League meta.
              </p>
              <p className="text-[11px] text-slate-200 leading-relaxed mt-2">
                Pick a format below to examine tier lists, trending cards, and tournament results.
              </p>
            </div>
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
