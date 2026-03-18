import { getArchetype, getArchetypeSlugs } from "@/app/lib/data";
import { TierBadge } from "@/app/components/tier-badge";
import { SpriteRow } from "@/app/components/sprite-row";
import { StatCard } from "@/app/components/stat-card";
import { formatPct, formatPlacement } from "@/app/lib/utils";

export function generateStaticParams() {
  return getArchetypeSlugs().map((slug) => ({ slug }));
}

export default async function ArchetypeDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const arch = getArchetype(slug);

  return (
    <div className="space-y-8">
      <div>
        <div className="flex items-center gap-3 mb-2">
          <TierBadge tier={arch.tier} />
          <SpriteRow filenames={arch.sprite_filenames ?? []} size={32} />
          <h1 className="font-display text-2xl font-bold text-slate-100">
            {arch.archetype}
          </h1>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 mt-4">
          <StatCard label="Meta Share" value={formatPct(arch.meta_share)} />
          <StatCard label="Decks" value={arch.deck_count} />
          <StatCard label="Best Finish" value={formatPlacement(arch.best_placement)} />
          <StatCard label="Core Cards" value={arch.core_cards.length} />
        </div>
      </div>

      {/* Core Cards */}
      <section>
        <h2 className="font-display text-lg font-semibold text-slate-100 mb-4">
          Core Cards
          <span className="text-sm font-normal text-surface-300 ml-2">80%+ inclusion</span>
        </h2>
        <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-600 text-xs text-surface-300 uppercase tracking-wider">
                  <th className="text-left px-4 py-3">Card</th>
                  <th className="text-right px-4 py-3">Inclusion</th>
                  <th className="text-right px-4 py-3">Avg Copies</th>
                  <th className="text-right px-4 py-3 hidden sm:table-cell">Decks</th>
                </tr>
              </thead>
              <tbody>
                {arch.core_cards.map((card, i) => (
                  <tr
                    key={card.card_name}
                    className="border-b border-surface-700 hover:bg-surface-700/50 transition-colors animate-row-reveal"
                    style={{ animationDelay: `${i * 20}ms` }}
                  >
                    <td className="px-4 py-3 text-slate-200">{card.card_name}</td>
                    <td className="px-4 py-3 text-right font-mono tabular-nums">
                      {card.inclusion_pct.toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-right font-mono tabular-nums">
                      {card.avg_copies.toFixed(1)}
                    </td>
                    <td className="px-4 py-3 text-right text-surface-300 font-mono tabular-nums hidden sm:table-cell">
                      {card.decks_with}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* All Cards */}
      <section>
        <h2 className="font-display text-lg font-semibold text-slate-100 mb-4">
          All Cards
          <span className="text-sm font-normal text-surface-300 ml-2">
            {arch.all_cards.length} unique cards
          </span>
        </h2>
        <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-600 text-xs text-surface-300 uppercase tracking-wider">
                  <th className="text-left px-4 py-3">Card</th>
                  <th className="text-right px-4 py-3">Inclusion</th>
                  <th className="text-right px-4 py-3">Avg Copies</th>
                </tr>
              </thead>
              <tbody>
                {arch.all_cards.map((card) => (
                  <tr
                    key={card.card_name}
                    className="border-b border-surface-700 hover:bg-surface-700/50 transition-colors"
                  >
                    <td className="px-4 py-3 text-slate-300">{card.card_name}</td>
                    <td className="px-4 py-3 text-right font-mono tabular-nums text-surface-300">
                      {card.inclusion_pct.toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-right font-mono tabular-nums text-surface-300">
                      {card.avg_copies.toFixed(1)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Tournament Results */}
      {arch.results && arch.results.length > 0 && (
        <section>
          <h2 className="font-display text-lg font-semibold text-slate-100 mb-4">
            Results
            <span className="text-sm font-normal text-surface-300 ml-2">
              {arch.results.length} placements
            </span>
          </h2>
          <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-surface-600 text-xs text-surface-300 uppercase tracking-wider">
                    <th className="text-left px-4 py-3">Date</th>
                    <th className="text-left px-4 py-3">City League</th>
                    <th className="text-right px-4 py-3">Standing</th>
                    <th className="text-left px-4 py-3 hidden sm:table-cell">Player</th>
                  </tr>
                </thead>
                <tbody>
                  {arch.results.map((result, i) => (
                    <tr
                      key={`${result.date}-${result.standing}-${result.player_name}`}
                      className="border-b border-surface-700 hover:bg-surface-700/50 transition-colors"
                    >
                      <td className="px-4 py-3 font-mono text-xs text-surface-300">
                        {result.date}
                      </td>
                      <td className="px-4 py-3 text-slate-300 text-sm">
                        {result.tournament_name}
                      </td>
                      <td className="px-4 py-3 text-right font-mono tabular-nums">
                        {formatPlacement(result.standing)}
                      </td>
                      <td className="px-4 py-3 text-sm text-surface-300 hidden sm:table-cell">
                        {result.player_name}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
