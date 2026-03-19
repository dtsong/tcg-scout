"use client";

import { DataTable } from "@/app/components/data-table";
import type { SynergyPair } from "@/app/lib/types";

export function SynergyClient({
  pairs,
  format,
}: {
  pairs: SynergyPair[];
  format: string;
}) {
  const columns = [
    {
      key: "card_a",
      header: "Card A",
      render: (row: SynergyPair) => (
        <span className="text-sm text-slate-200">{row.card_a}</span>
      ),
      sortValue: (row: SynergyPair) => row.card_a,
    },
    {
      key: "card_b",
      header: "Card B",
      render: (row: SynergyPair) => (
        <span className="text-sm text-slate-200">{row.card_b}</span>
      ),
      sortValue: (row: SynergyPair) => row.card_b,
    },
    {
      key: "lift",
      header: "Lift",
      render: (row: SynergyPair) => (
        <span className="font-mono text-sm text-blue-400 tabular-nums">
          {row.lift.toFixed(2)}x
        </span>
      ),
      sortValue: (row: SynergyPair) => row.lift,
      align: "right" as const,
    },
    {
      key: "support",
      header: "Co-play",
      render: (row: SynergyPair) => (
        <span className="font-mono text-sm text-slate-300 tabular-nums">
          {row.support}
        </span>
      ),
      sortValue: (row: SynergyPair) => row.support,
      align: "right" as const,
    },
    {
      key: "jaccard",
      header: "Overlap",
      render: (row: SynergyPair) => (
        <span className="font-mono text-sm text-surface-300 tabular-nums">
          {(row.jaccard * 100).toFixed(0)}%
        </span>
      ),
      sortValue: (row: SynergyPair) => row.jaccard,
      align: "right" as const,
      hideOnMobile: true,
    },
    {
      key: "archetypes",
      header: "Archetypes",
      render: (row: SynergyPair) => (
        <span className="text-xs text-surface-400 truncate max-w-[200px] inline-block">
          {row.archetypes?.slice(0, 3).join(", ") || "-"}
        </span>
      ),
      hideOnMobile: true,
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-bold text-slate-100">
          Synergy Explorer
        </h1>
        <p className="text-sm text-surface-300 mt-1">
          Top {pairs.length} card pairs by co-occurrence lift -- cards that appear together
          more often than random chance would predict
        </p>
      </div>

      <DataTable
        data={pairs}
        columns={columns}
        searchKey={(row) => `${row.card_a} ${row.card_b}`}
        searchPlaceholder="Search card pairs..."
      />
    </div>
  );
}
