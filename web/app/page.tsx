import Link from "next/link";
import { ArrowRight, TrendingUp, Trophy, ShoppingCart, Calendar } from "lucide-react";
import { getMeta, getAceSpecs, getTrends, getWinningEdge } from "@/app/lib/data";
import { TierBadge } from "@/app/components/tier-badge";
import { StatCard } from "@/app/components/stat-card";
import { formatPct, daysUntil } from "@/app/lib/utils";

export default function Dashboard() {
  const meta = getMeta();
  const aceSpecs = getAceSpecs();
  const trends = getTrends();
  const winningEdge = getWinningEdge();

  const rotationDays = daysUntil(meta.rotation_date);
  const topArchetypes = meta.archetypes.filter((a) =>
    ["S", "A", "B"].includes(a.tier),
  );
  const surgingCards = trends.cards.slice(0, 5);
  const topEdge = winningEdge.slice(0, 5);
  const topAceSpecs = aceSpecs.slice(0, 5);

  return (
    <div className="space-y-10">
      {/* Hero */}
      <section className="relative rounded-lg bg-surface-800 border border-surface-600 p-6 sm:p-8 scanline-overlay">
        <div className="relative">
          <h1 className="font-display text-3xl sm:text-4xl font-bold text-slate-100">
            Scout
          </h1>
          <p className="mt-2 text-surface-300 max-w-2xl">
            JP Rotation Meta Intelligence — City League tournament data and competitive analysis
            for the post-rotation format.
          </p>
          <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-6">
            <StatCard label="Tournaments" value={meta.tournament_count.toLocaleString()} />
            <StatCard label="Decks Analyzed" value={meta.deck_count.toLocaleString()} />
            <StatCard
              label="Date Range"
              value={`${meta.date_range.start.slice(5)} — ${meta.date_range.end.slice(5)}`}
            />
            <div className="flex flex-col gap-1">
              <span className="text-sm text-surface-300 flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5" />
                Rotation
              </span>
              <span className="font-mono text-2xl font-medium text-accent tabular-nums">
                {rotationDays > 0 ? `${rotationDays}d` : "Live"}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Tier List Preview */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-xl font-semibold text-slate-100">
            Meta Tier List
          </h2>
          <Link
            href="/archetypes"
            className="text-sm text-accent hover:text-accent/80 flex items-center gap-1"
          >
            View all <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
        <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-600 text-xs text-surface-300 uppercase tracking-wider">
                <th className="text-left px-4 py-3">Tier</th>
                <th className="text-left px-4 py-3">Archetype</th>
                <th className="text-right px-4 py-3">Meta Share</th>
                <th className="text-right px-4 py-3 hidden sm:table-cell">Decks</th>
              </tr>
            </thead>
            <tbody>
              {topArchetypes.map((arch, i) => (
                <tr
                  key={arch.slug}
                  className="border-b border-surface-700 hover:bg-surface-700/50 transition-colors animate-row-reveal"
                  style={{ animationDelay: `${i * 30}ms` }}
                >
                  <td className="px-4 py-3">
                    <TierBadge tier={arch.tier} />
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/archetypes/${arch.slug}`}
                      className="text-slate-200 hover:text-accent transition-colors"
                    >
                      {arch.archetype}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums">
                    {formatPct(arch.meta_share)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums text-surface-300 hidden sm:table-cell">
                    {arch.deck_count}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Quick Insights Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Surging Cards */}
        <section className="bg-surface-800 border border-surface-600 rounded-lg p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-display text-sm font-semibold text-slate-200 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-signal-up" />
              Surging Cards
            </h3>
            <Link href="/trends" className="text-xs text-accent hover:text-accent/80">
              More
            </Link>
          </div>
          <div className="space-y-3">
            {surgingCards.map((card) => (
              <div key={card.card_name} className="flex items-center justify-between">
                <span className="text-sm text-slate-300 truncate mr-2">{card.card_name}</span>
                <span className="font-mono text-xs text-signal-up whitespace-nowrap">
                  +{card.delta.toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* Winning Edge */}
        <section className="bg-surface-800 border border-surface-600 rounded-lg p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-display text-sm font-semibold text-slate-200 flex items-center gap-2">
              <Trophy className="w-4 h-4 text-tier-s" />
              Winning Edge
            </h3>
            <Link href="/trends" className="text-xs text-accent hover:text-accent/80">
              More
            </Link>
          </div>
          <div className="space-y-3">
            {topEdge.map((card) => (
              <div key={card.card_name} className="flex items-center justify-between">
                <span className="text-sm text-slate-300 truncate mr-2">{card.card_name}</span>
                <span className="font-mono text-xs text-tier-s whitespace-nowrap">
                  +{card.edge.toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* ACE SPEC Distribution */}
        <section className="bg-surface-800 border border-surface-600 rounded-lg p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-display text-sm font-semibold text-slate-200 flex items-center gap-2">
              <ShoppingCart className="w-4 h-4 text-tier-rogue" />
              ACE SPECs
            </h3>
            <Link href="/buylist" className="text-xs text-accent hover:text-accent/80">
              Buy List
            </Link>
          </div>
          <div className="space-y-3">
            {topAceSpecs.map((spec) => (
              <div key={spec.card_name} className="flex items-center justify-between">
                <span className="text-sm text-slate-300 truncate mr-2">{spec.card_name}</span>
                <span className="font-mono text-xs text-surface-300 whitespace-nowrap">
                  {formatPct(spec.usage_pct)}
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* Nav Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { href: "/archetypes", title: "Archetypes", desc: `${meta.archetypes.length} decks tracked` },
          { href: "/buylist", title: "Buy List", desc: "Priority acquisition guide" },
          { href: "/trends", title: "Trends", desc: "Usage shifts & winning edge" },
          { href: "/champions", title: "Champions League", desc: "Fukuoka CL decklists" },
        ].map(({ href, title, desc }) => (
          <Link
            key={href}
            href={href}
            className="group bg-surface-800 border border-surface-600 rounded-lg p-4 hover:border-surface-400 transition-colors"
          >
            <h3 className="font-display font-semibold text-slate-200 group-hover:text-accent transition-colors">
              {title}
            </h3>
            <p className="text-sm text-surface-300 mt-1">{desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
