import Link from "next/link";
import { Crosshair } from "lucide-react";
import { getFormats, getDefaultFormat } from "@/app/lib/data";
import { HomeFormatSections } from "@/app/components/home-format-sections";

export default function FormatSelectorPage() {
  const formats = getFormats();
  const defaultFormat = getDefaultFormat();

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
                I&apos;m here to help you explore the Japanese City League and TPCi metas.
              </p>
              <p className="text-[11px] text-slate-200 leading-relaxed mt-1.5">
                Pick a format below to examine tier lists, trending cards, and tournament results.
              </p>
            </div>
          </div>

          <HomeFormatSections formats={formats} />

          {/* About & Methodology */}
          <div className="mt-10 pt-8 border-t border-surface-700 space-y-6">
            <div>
              <h3 className="font-display text-base font-semibold text-slate-100 mb-2">
                About the Data
              </h3>
              <p className="text-sm text-surface-300 leading-relaxed">
                Scout aggregates results from Japan&apos;s City League tournaments (64-player events held daily across the country) to provide an early look at each format&apos;s competitive meta before sets release internationally. Active formats are refreshed daily.
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
                New here?{" "}
                <Link href="/start" className="text-accent hover:text-accent/80 transition-colors">
                  Check out the quickstart
                </Link>{" "}
                to get oriented, or{" "}
                <Link href={`/${defaultFormat}/guide`} className="text-accent hover:text-accent/80 transition-colors">
                  read the guide
                </Link>{" "}
                for details. Have feedback or feature requests? Reach out:
              </p>
              <div className="flex items-center gap-4 mt-2">
                <a
                  href="https://github.com/dtsong/tcg-scout"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 text-xs text-surface-300 hover:text-slate-200 transition-colors"
                >
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" /></svg>
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
