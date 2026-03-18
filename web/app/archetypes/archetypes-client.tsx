"use client";

import Link from "next/link";
import { TierBadge } from "@/app/components/tier-badge";
import { MetaBarChart } from "@/app/components/meta-bar-chart";
import { DataTable } from "@/app/components/data-table";
import { formatPct, formatPlacement } from "@/app/lib/utils";
import type { ArchetypeSummary, Tier } from "@/app/lib/types";

export function ArchetypesClient({ archetypes }: { archetypes: ArchetypeSummary[] }) {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-[family-name:var(--font-display)] text-2xl font-bold text-slate-100">
          Archetypes
        </h1>
        <p className="text-sm text-surface-300 mt-1">
          {archetypes.length} archetypes tracked across all tiers
        </p>
      </div>

      <div className="bg-surface-800 border border-surface-600 rounded-lg p-4 sm:p-6">
        <h2 className="font-[family-name:var(--font-display)] text-sm font-semibold text-slate-200 mb-4">
          Top 20 Meta Shares
        </h2>
        <MetaBarChart data={archetypes} />
      </div>

      <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
        <DataTable
          data={archetypes}
          searchKey={(a) => a.archetype}
          searchPlaceholder="Search archetypes..."
          columns={[
            {
              key: "tier",
              header: "Tier",
              render: (a) => <TierBadge tier={a.tier as Tier} />,
              sortValue: (a) => {
                const order: Record<string, number> = { S: 0, A: 1, B: 2, C: 3, Rogue: 4 };
                return order[a.tier] ?? 5;
              },
            },
            {
              key: "archetype",
              header: "Archetype",
              render: (a) => (
                <Link
                  href={`/archetypes/${a.slug}`}
                  className="text-slate-200 hover:text-accent transition-colors"
                >
                  {a.archetype}
                </Link>
              ),
              sortValue: (a) => a.archetype,
            },
            {
              key: "meta_share",
              header: "Meta Share",
              align: "right",
              render: (a) => (
                <span className="font-[family-name:var(--font-mono)] tabular-nums">
                  {formatPct(a.meta_share)}
                </span>
              ),
              sortValue: (a) => a.meta_share,
            },
            {
              key: "deck_count",
              header: "Decks",
              align: "right",
              hideOnMobile: true,
              render: (a) => (
                <span className="font-[family-name:var(--font-mono)] tabular-nums text-surface-300">
                  {a.deck_count}
                </span>
              ),
              sortValue: (a) => a.deck_count,
            },
            {
              key: "best_placement",
              header: "Best",
              align: "right",
              hideOnMobile: true,
              render: (a) => (
                <span className="text-surface-300">
                  {formatPlacement(a.best_placement)}
                </span>
              ),
              sortValue: (a) => a.best_placement,
            },
          ]}
        />
      </div>
    </div>
  );
}
