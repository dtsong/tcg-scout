"use client";

import Link from "next/link";
import { StatCard } from "@/app/components/stat-card";
import { TierBadge } from "@/app/components/tier-badge";
import { formatPct } from "@/app/lib/utils";
import { cn } from "@/app/lib/utils";
import type { CardDetail, CardArchetype, SynergyPartner, CardAnalysisArchetype } from "@/app/lib/types";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
} from "recharts";

function generateVerdict(card: CardDetail): string {
  const archetypes = card.archetypes || [];
  const sCount = archetypes.filter((a) => a.tier === "S").length;
  const aCount = archetypes.filter((a) => a.tier === "A").length;
  const topTierCount = sCount + aCount;
  const isFourOf = card.avg_copies >= 3.5;
  const copyLabel = isFourOf ? "4-of" : `${card.avg_copies.toFixed(0)}-of`;

  if (topTierCount >= 2 && isFourOf) {
    const tiers: string[] = [];
    if (sCount) tiers.push(`${sCount} S-tier`);
    if (aCount) tiers.push(`${aCount} A-tier`);
    return `Core ${copyLabel} in ${tiers.join(" and ")} archetypes`;
  }

  if (topTierCount >= 1) {
    return `Key card in ${topTierCount} top-tier archetype${topTierCount > 1 ? "s" : ""}`;
  }

  if (card.unique_archetypes >= 5) {
    return `Format staple across ${card.unique_archetypes} archetypes`;
  }
  if (card.unique_archetypes >= 2) {
    return `Flex tech in ${card.unique_archetypes} archetypes`;
  }
  return `Niche pick (${card.total_appearances} appearances)`;
}

function CopyDistributionChart({ data }: { data: { copies: number; count: number }[] }) {
  if (data.length === 0) return null;
  const barColors = ["#64748b", "#94a3b8", "#cbd5e1", "#e2e8f0"];
  return (
    <div className="h-32">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <XAxis
            dataKey="copies"
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => `${v}x`}
          />
          <YAxis hide />
          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
            {data.map((_, i) => (
              <Cell key={i} fill={barColors[i % barColors.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function UsageTrendChart({ data }: { data: { week: string; usage_pct: number }[] }) {
  if (data.length < 2) return null;
  return (
    <div className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <defs>
            <linearGradient id="usageGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="week"
            tick={{ fill: "#64748b", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => {
              const d = new Date(v);
              return `${d.getMonth() + 1}/${d.getDate()}`;
            }}
          />
          <YAxis
            tick={{ fill: "#64748b", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => `${v}%`}
            width={40}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1e293b",
              border: "1px solid #334155",
              borderRadius: "8px",
              fontSize: "12px",
            }}
            labelFormatter={(v) => `Week of ${v}`}
            formatter={(value) => [`${Number(value).toFixed(1)}%`, "Usage"]}
          />
          <Area
            type="monotone"
            dataKey="usage_pct"
            stroke="#3b82f6"
            fill="url(#usageGradient)"
            strokeWidth={2}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function DeltaValue({ delta }: { delta: number }) {
  if (delta === 0) return <span className="text-xs font-mono text-surface-400">0.0</span>;
  const positive = delta > 0;
  return (
    <span className={`text-xs font-mono tabular-nums ${positive ? "text-emerald-400" : "text-red-400"}`}>
      {positive ? "+" : ""}{delta.toFixed(1)}
    </span>
  );
}

function ArchetypeRow({ archetype, format, delta }: { archetype: CardArchetype; format: string; delta?: number }) {
  return (
    <div className="flex items-center justify-between py-2.5 px-3 rounded hover:bg-surface-700/40 transition-colors">
      <div className="flex items-center gap-2.5 min-w-0">
        <TierBadge tier={archetype.tier} />
        <Link
          href={`/${format}/archetypes/${archetype.slug}`}
          className="text-sm text-slate-200 hover:text-accent transition-colors truncate"
        >
          {archetype.name}
        </Link>
      </div>
      <div className="flex items-center gap-4 shrink-0">
        <span className="font-mono text-xs text-surface-300 tabular-nums">
          {archetype.avg_copies.toFixed(1)}x
        </span>
        <span className="font-mono text-xs text-surface-400 tabular-nums w-12 text-right">
          {archetype.usage_count} decks
        </span>
        {delta !== undefined && (
          <span className="w-12 text-right">
            <DeltaValue delta={delta} />
          </span>
        )}
      </div>
    </div>
  );
}

export function CardDetailClient({
  card,
  format,
  top4Deltas,
}: {
  card: CardDetail;
  format: string;
  top4Deltas?: CardAnalysisArchetype[];
}) {
  const deltaBySlug = top4Deltas
    ? new Map(top4Deltas.map((d) => [d.slug, d.delta_vs_field]))
    : undefined;
  const verdict = generateVerdict(card);

  return (
    <div className="space-y-8">
      {/* Hero */}
      <div>
        <div className="flex items-start gap-4">
          {card.image_url && (
            <img
              src={card.image_url}
              alt={card.card_name}
              className="w-24 h-auto rounded-lg shadow-lg"
            />
          )}
          <div className="flex-1 min-w-0">
            <h1 className="font-display text-2xl font-bold text-slate-100">
              {card.card_name}
            </h1>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span
                className={cn(
                  "text-[10px] font-mono px-1.5 py-0.5 rounded",
                  card.category === "Pokemon" && "bg-blue-500/15 text-blue-400",
                  card.category === "Trainer" && "bg-amber-500/15 text-amber-400",
                  card.category === "Energy" && "bg-emerald-500/15 text-emerald-400",
                )}
              >
                {card.category}
              </span>
              {card.set_code && card.set_number && (
                <span className="text-xs font-mono text-surface-400">
                  {card.set_code.toUpperCase()} #{card.set_number}
                </span>
              )}
              {card.rarity && (
                <span className="text-xs text-surface-400">{card.rarity}</span>
              )}
            </div>
            <p className="text-sm text-surface-300 mt-2">{verdict}</p>
          </div>
        </div>

        {/* Stat row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 mt-6">
          <StatCard label="Usage" value={formatPct(card.usage_pct)} />
          <StatCard label="Avg Copies" value={card.avg_copies.toFixed(1)} />
          <StatCard label="Archetypes" value={card.unique_archetypes} />
          <StatCard label="Win Rate Proxy" value={card.win_rate_proxy.toFixed(2)} />
        </div>
      </div>

      {/* Copy Distribution */}
      {card.copy_distribution.length > 0 && (
        <section>
          <h2 className="font-display text-lg font-semibold text-slate-100 mb-1">
            Copy Distribution
          </h2>
          <p className="text-xs text-surface-400 mb-3">
            How many copies players run across {card.total_appearances} decklists
          </p>
          <div className="bg-surface-800 border border-surface-600 rounded-lg p-4">
            <CopyDistributionChart data={card.copy_distribution} />
          </div>
        </section>
      )}

      {/* Archetype Usage */}
      {card.archetypes.length > 0 && (
        <section>
          <h2 className="font-display text-lg font-semibold text-slate-100 mb-1">
            Archetype Usage
          </h2>
          <p className="text-xs text-surface-400 mb-3">
            Which archetypes run this card, sorted by usage
          </p>
          <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
            <div className="p-1.5 space-y-0.5">
              {card.archetypes.map((arch) => (
                <ArchetypeRow key={arch.slug} archetype={arch} format={format} delta={deltaBySlug?.get(arch.slug)} />
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Synergy Partners */}
      {card.synergy_partners && card.synergy_partners.length > 0 && (
        <section>
          <h2 className="font-display text-lg font-semibold text-slate-100 mb-1">
            Pairs Well With
          </h2>
          <p className="text-xs text-surface-400 mb-3">
            Cards that appear together more often than expected (sorted by lift)
          </p>
          <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
            <div className="p-1.5 space-y-0.5">
              {card.synergy_partners.slice(0, 10).map((partner) => (
                <div
                  key={partner.card_name}
                  className="flex items-center justify-between py-2.5 px-3 rounded hover:bg-surface-700/40 transition-colors"
                >
                  <span className="text-sm text-slate-200 truncate">
                    {partner.card_name}
                  </span>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-400">
                      {partner.lift.toFixed(1)}x lift
                    </span>
                    <span className="font-mono text-xs text-surface-400 tabular-nums">
                      {partner.support} decks
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Usage Trend */}
      {card.weekly_usage.length >= 2 && (
        <section>
          <h2 className="font-display text-lg font-semibold text-slate-100 mb-1">
            Usage Trend
          </h2>
          <p className="text-xs text-surface-400 mb-3">
            Weekly inclusion rate over time
          </p>
          <div className="bg-surface-800 border border-surface-600 rounded-lg p-4">
            <UsageTrendChart data={card.weekly_usage} />
          </div>
        </section>
      )}
    </div>
  );
}
