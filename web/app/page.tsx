import Link from "next/link";
import { Crosshair, ChevronRight, Github } from "lucide-react";
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
      <div className="flex-1 flex items-start justify-center px-4 py-8 sm:py-12">
        <div className="w-full max-w-4xl">
          {/* Professor Oak Welcome — side by side on desktop */}
          <div className="flex flex-col sm:flex-row items-center gap-4 sm:gap-6 mb-8 sm:mb-10">
            <div className="relative shrink-0">
              <div
                className="absolute inset-0 rounded-full blur-2xl opacity-30"
                style={{ background: "radial-gradient(circle, #f59e0b 0%, transparent 70%)" }}
              />
              <div
                className="absolute bottom-0 left-1/2 -translate-x-1/2 w-20 h-5 rounded-full opacity-20 blur-sm"
                style={{ background: "radial-gradient(ellipse, #f59e0b 0%, transparent 70%)" }}
              />
              <img
                src="/images/professor-oak.png"
                alt="Professor Oak"
                width={96}
                height={96}
                className="relative"
                style={{ imageRendering: "pixelated" }}
              />
            </div>
            <div className="relative bg-surface-800 border-2 border-surface-500 rounded-xl px-5 py-3.5 flex-1 max-w-lg" style={{ fontFamily: "var(--font-pokemon), monospace" }}>
              {/* Speech arrow — points left on desktop, up on mobile */}
              <div className="hidden sm:block absolute top-1/2 -left-2 -translate-y-1/2 w-3 h-3 bg-surface-800 border-l-2 border-b-2 border-surface-500 rotate-45" />
              <div className="sm:hidden absolute -top-2 left-8 w-3 h-3 bg-surface-800 border-l-2 border-t-2 border-surface-500 rotate-45" />
              <p className="text-[11px] text-slate-200 leading-relaxed">
                Welcome to the world of competitive Pokemon TCG!
              </p>
              <p className="text-[11px] text-slate-200 leading-relaxed mt-1.5">
                I&apos;m here to help you explore Japan&apos;s City League meta.
              </p>
              <p className="text-[11px] text-slate-200 leading-relaxed mt-1.5">
                Pick a format below to examine tier lists, trending cards, and tournament results.
              </p>
            </div>
          </div>

          {/* Format cards */}
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

          {/* About & Methodology */}
          <div className="mt-10 pt-8 border-t border-surface-700 space-y-6">
            <div>
              <h3 className="font-display text-base font-semibold text-slate-100 mb-2">
                About the Data
              </h3>
              <p className="text-sm text-surface-300 leading-relaxed">
                Scout aggregates results from Japan&apos;s City League tournaments (64-player events held daily across the country) to provide an early look at each format&apos;s competitive meta before sets release internationally. Data is refreshed daily.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div>
                <h4 className="text-sm font-semibold text-slate-200 mb-1.5">Tier Methodology</h4>
                <p className="text-sm text-surface-300 leading-relaxed">
                  Archetypes are assigned tiers based on meta share: S (15%+), A (8%+), B (3%+), C (1%+), and Rogue (under 1%). Weighted shares factor in placement finish -- winning decks are valued higher than raw counts.
                </p>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-slate-200 mb-1.5">Trends & Winning Edge</h4>
                <p className="text-sm text-surface-300 leading-relaxed">
                  Trends compare card usage between the first and second half of each format&apos;s data window. The Winning Edge highlights cards that appear more often in 1st-place decks than the general field across S/A/B tier archetypes.
                </p>
              </div>
            </div>

            <div className="pt-4 border-t border-surface-700">
              <p className="text-xs text-surface-300">
                Tournament results sourced from{" "}
                <a href="https://limitlesstcg.com" target="_blank" rel="noopener noreferrer" className="text-accent hover:text-accent/80">
                  LimitlessTCG
                </a>
                . Champions League decklists from{" "}
                <a href="https://pokemon-card.com" target="_blank" rel="noopener noreferrer" className="text-accent hover:text-accent/80">
                  pokemon-card.com
                </a>
                {" "}(official Japanese Pokemon TCG site). Scout is a fan project and is not affiliated with or endorsed by The Pokemon Company.
              </p>
              <p className="text-xs text-surface-300 mt-3">
                Have feedback or feature requests? Reach out:
              </p>
              <div className="flex items-center gap-4 mt-2">
                <a
                  href="https://github.com/dtsong/tcg-scout"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 text-xs text-surface-300 hover:text-slate-200 transition-colors"
                >
                  <Github className="w-3.5 h-3.5" />
                  GitHub
                </a>
                <a
                  href="https://x.com/pokedansong"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 text-xs text-surface-300 hover:text-slate-200 transition-colors"
                >
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" /></svg>
                  @pokedansong
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
