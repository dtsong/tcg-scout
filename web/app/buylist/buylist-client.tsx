"use client";

import { useState } from "react";
import { DataTable } from "@/app/components/data-table";
import { UrgencyBadge } from "@/app/components/urgency-badge";
import { formatPct } from "@/app/lib/utils";
import { cn } from "@/app/lib/utils";
import type { BuylistCard, StapleCard, Urgency } from "@/app/lib/types";

const tabs = ["Full List", "Staples", "Flex"] as const;
type Tab = (typeof tabs)[number];

export function BuylistClient({
  buylist,
  staples,
  flex,
}: {
  buylist: BuylistCard[];
  staples: StapleCard[];
  flex: StapleCard[];
}) {
  const [activeTab, setActiveTab] = useState<Tab>("Full List");
  const [urgencyFilter, setUrgencyFilter] = useState<Urgency | "all">("all");

  const filteredBuylist =
    urgencyFilter === "all"
      ? buylist
      : buylist.filter((c) => c.urgency === urgencyFilter);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-[family-name:var(--font-display)] text-2xl font-bold text-slate-100">
          Buy List
        </h1>
        <p className="text-sm text-surface-300 mt-1">
          Prioritized acquisition guide — {buylist.length} cards across S/A/B tier archetypes
        </p>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-surface-600">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              "px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px",
              activeTab === tab
                ? "border-accent text-accent"
                : "border-transparent text-surface-300 hover:text-slate-200",
            )}
          >
            {tab}
            <span className="ml-1.5 text-xs text-surface-400">
              {tab === "Full List" ? buylist.length : tab === "Staples" ? staples.length : flex.length}
            </span>
          </button>
        ))}
      </div>

      {activeTab === "Full List" && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <span className="text-xs text-surface-300 mr-1">Filter:</span>
            {(["all", "URGENT", "HIGH", "MODERATE"] as const).map((u) => (
              <button
                key={u}
                onClick={() => setUrgencyFilter(u)}
                className={cn(
                  "px-2.5 py-1 text-xs rounded-md transition-colors",
                  urgencyFilter === u
                    ? "bg-surface-600 text-slate-200"
                    : "text-surface-400 hover:text-slate-300 hover:bg-surface-700",
                )}
              >
                {u === "all" ? "All" : u}
              </button>
            ))}
          </div>

          <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
            <DataTable
              data={filteredBuylist}
              searchKey={(c) => c.card_name}
              searchPlaceholder="Search cards..."
              columns={[
                {
                  key: "card_name",
                  header: "Card",
                  render: (c) => <span className="text-slate-200">{c.card_name}</span>,
                  sortValue: (c) => c.card_name,
                },
                {
                  key: "urgency",
                  header: "Urgency",
                  render: (c) => <UrgencyBadge urgency={c.urgency} />,
                  sortValue: (c) => ({ URGENT: 0, HIGH: 1, MODERATE: 2 }[c.urgency]),
                },
                {
                  key: "priority",
                  header: "Priority",
                  align: "right",
                  render: (c) => (
                    <span className="font-[family-name:var(--font-mono)] tabular-nums">
                      {c.priority_score.toFixed(1)}
                    </span>
                  ),
                  sortValue: (c) => c.priority_score,
                },
                {
                  key: "avg_copies",
                  header: "Avg Copies",
                  align: "right",
                  hideOnMobile: true,
                  render: (c) => (
                    <span className="font-[family-name:var(--font-mono)] tabular-nums text-surface-300">
                      {c.avg_copies.toFixed(1)}
                    </span>
                  ),
                  sortValue: (c) => c.avg_copies,
                },
                {
                  key: "inclusion",
                  header: "Inclusion",
                  align: "right",
                  hideOnMobile: true,
                  render: (c) => (
                    <span className="font-[family-name:var(--font-mono)] tabular-nums text-surface-300">
                      {formatPct(c.inclusion_rate * 100)}
                    </span>
                  ),
                  sortValue: (c) => c.inclusion_rate,
                },
                {
                  key: "archetypes",
                  header: "Archetypes",
                  hideOnMobile: true,
                  render: (c) => {
                    const display = c.archetypes.slice(0, 2).join(", ");
                    const more = c.archetypes.length > 2 ? ` +${c.archetypes.length - 2}` : "";
                    return (
                      <span className="text-xs text-surface-300">
                        {display}{more}
                      </span>
                    );
                  },
                },
              ]}
            />
          </div>
        </div>
      )}

      {activeTab === "Staples" && (
        <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
          <DataTable
            data={staples}
            searchKey={(c) => c.card_name}
            searchPlaceholder="Search staples..."
            columns={[
              {
                key: "card_name",
                header: "Card",
                render: (c) => <span className="text-slate-200">{c.card_name}</span>,
                sortValue: (c) => c.card_name,
              },
              {
                key: "usage_pct",
                header: "Usage",
                align: "right",
                render: (c) => (
                  <span className="font-[family-name:var(--font-mono)] tabular-nums">
                    {formatPct(c.usage_pct)}
                  </span>
                ),
                sortValue: (c) => c.usage_pct,
              },
              {
                key: "avg_copies",
                header: "Avg Copies",
                align: "right",
                render: (c) => (
                  <span className="font-[family-name:var(--font-mono)] tabular-nums text-surface-300">
                    {c.avg_copies.toFixed(1)}
                  </span>
                ),
                sortValue: (c) => c.avg_copies,
              },
              {
                key: "deck_count",
                header: "Decks",
                align: "right",
                hideOnMobile: true,
                render: (c) => (
                  <span className="font-[family-name:var(--font-mono)] tabular-nums text-surface-300">
                    {c.deck_count}
                  </span>
                ),
                sortValue: (c) => c.deck_count,
              },
            ]}
          />
        </div>
      )}

      {activeTab === "Flex" && (
        <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
          <DataTable
            data={flex}
            searchKey={(c) => c.card_name}
            searchPlaceholder="Search flex cards..."
            columns={[
              {
                key: "card_name",
                header: "Card",
                render: (c) => <span className="text-slate-200">{c.card_name}</span>,
                sortValue: (c) => c.card_name,
              },
              {
                key: "usage_pct",
                header: "Usage",
                align: "right",
                render: (c) => (
                  <span className="font-[family-name:var(--font-mono)] tabular-nums">
                    {formatPct(c.usage_pct)}
                  </span>
                ),
                sortValue: (c) => c.usage_pct,
              },
              {
                key: "avg_copies",
                header: "Avg Copies",
                align: "right",
                render: (c) => (
                  <span className="font-[family-name:var(--font-mono)] tabular-nums text-surface-300">
                    {c.avg_copies.toFixed(1)}
                  </span>
                ),
                sortValue: (c) => c.avg_copies,
              },
              {
                key: "deck_count",
                header: "Decks",
                align: "right",
                hideOnMobile: true,
                render: (c) => (
                  <span className="font-[family-name:var(--font-mono)] tabular-nums text-surface-300">
                    {c.deck_count}
                  </span>
                ),
                sortValue: (c) => c.deck_count,
              },
            ]}
          />
        </div>
      )}
    </div>
  );
}
