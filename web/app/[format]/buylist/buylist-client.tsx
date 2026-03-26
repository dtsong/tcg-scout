"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { DataTable } from "@/app/components/data-table";
import { DateFilter } from "@/app/components/date-filter";
import { useDateFilter, fetchWindowedData } from "@/app/components/date-filter-provider";
import { ExternalLink } from "lucide-react";
import { formatPct, cn } from "@/app/lib/utils";
import { CardLink } from "@/app/components/card-link";
import type { BuylistCard, StapleCard, TimeWindow } from "@/app/lib/types";

const tabs = ["Full List", "Staples", "Flex"] as const;
type Tab = (typeof tabs)[number];

export function BuylistClient({
  buylist: initialBuylist,
  staples: initialStaples,
  flex: initialFlex,
  dateRange,
}: {
  buylist: BuylistCard[];
  staples: StapleCard[];
  flex: StapleCard[];
  dateRange: { start: string; end: string };
}) {
  const [activeTab, setActiveTab] = useState<Tab>("Full List");
  const { format } = useParams<{ format: string }>();
  const { activeWindow, setWindow } = useDateFilter();

  const [buylist, setBuylist] = useState(initialBuylist);
  const [staples, setStaples] = useState(initialStaples);
  const [flex, setFlex] = useState(initialFlex);

  const cardNameColumn = {
    key: "card_name" as const,
    header: "Card",
    render: (c: { card_name: string }) => <CardLink name={c.card_name} className="text-slate-200" />,
    sortValue: (c: { card_name: string }) => c.card_name,
  };

  const fetchWindowData = useCallback(
    async (window: TimeWindow) => {
      if (window === "all" || window === "custom") {
        setBuylist(initialBuylist);
        setStaples(initialStaples);
        setFlex(initialFlex);
        return;
      }

      const suffix = window === "7d" ? "-7d" : "-30d";

      const [newBuylist, newStaples, newFlex] = await Promise.all([
        fetchWindowedData<BuylistCard[]>(format, "buylist.json", suffix),
        fetchWindowedData<StapleCard[]>(format, "staples.json", suffix),
        fetchWindowedData<StapleCard[]>(format, "flex.json", suffix),
      ]);

      if (newBuylist) setBuylist(newBuylist);
      if (newStaples) setStaples(newStaples);
      if (newFlex) setFlex(newFlex);
    },
    [format, initialBuylist, initialStaples, initialFlex],
  );

  useEffect(() => {
    fetchWindowData(activeWindow);
  }, [activeWindow, fetchWindowData]);

  const handleWindowChange = useCallback(
    (window: TimeWindow, range?: { start: string; end: string }) => {
      setWindow(window, range);
    },
    [setWindow],
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold text-slate-100">
            Buy List
          </h1>
          <p className="text-sm text-surface-300 mt-1">
            Prioritized acquisition guide: {buylist.length} cards across S/A/B tier archetypes{" "}
            <Link href={`/${format}/guide#buy-list`} className="text-accent hover:text-accent/80 transition-colors">
              How this works &rarr;
            </Link>
          </p>
        </div>
        <DateFilter activeWindow={activeWindow} onWindowChange={handleWindowChange} dateRange={dateRange} customRange={undefined} />
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
          <div className="bg-surface-800 border border-surface-600 rounded-md overflow-hidden">
            <DataTable
              data={buylist}
              searchKey={(c) => c.card_name}
              searchPlaceholder="Search cards..."
              columns={[
                cardNameColumn,
                {
                  key: "buy",
                  header: "",
                  render: (c) => (
                    <a
                      href={`https://www.tcgplayer.com/search/pokemon/product?q=${encodeURIComponent(c.card_name)}&view=grid`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent hover:text-accent/80 inline-flex items-center gap-1 text-xs"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">TCGPlayer</span>
                    </a>
                  ),
                },
                {
                  key: "priority",
                  header: "Priority",
                  align: "right",
                  render: (c) => (
                    <span className="font-mono tabular-nums">
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
                    <span className="font-mono tabular-nums text-surface-300">
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
                    <span className="font-mono tabular-nums text-surface-300">
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
        <div className="bg-surface-800 border border-surface-600 rounded-md overflow-hidden">
          <DataTable
            data={staples}
            searchKey={(c) => c.card_name}
            searchPlaceholder="Search staples..."
            columns={[
              cardNameColumn,
              {
                key: "usage_pct",
                header: "Usage",
                align: "right",
                render: (c) => (
                  <span className="font-mono tabular-nums">
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
                  <span className="font-mono tabular-nums text-surface-300">
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
                  <span className="font-mono tabular-nums text-surface-300">
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
        <div className="bg-surface-800 border border-surface-600 rounded-md overflow-hidden">
          <DataTable
            data={flex}
            searchKey={(c) => c.card_name}
            searchPlaceholder="Search flex cards..."
            columns={[
              cardNameColumn,
              {
                key: "usage_pct",
                header: "Usage",
                align: "right",
                render: (c) => (
                  <span className="font-mono tabular-nums">
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
                  <span className="font-mono tabular-nums text-surface-300">
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
                  <span className="font-mono tabular-nums text-surface-300">
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
