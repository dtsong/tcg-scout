"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { DataTable } from "@/app/components/data-table";
import { formatPct } from "@/app/lib/utils";
import { cn } from "@/app/lib/utils";
import type { CardSummary } from "@/app/lib/types";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

type CategoryFilter = "All" | "Pokemon" | "Trainer" | "Energy";

function TrendIcon({ direction }: { direction: string }) {
  switch (direction) {
    case "surging":
      return <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />;
    case "declining":
      return <TrendingDown className="w-3.5 h-3.5 text-red-400" />;
    default:
      return <Minus className="w-3.5 h-3.5 text-surface-400" />;
  }
}

function CategoryBadge({ category }: { category: string }) {
  const colors = {
    Pokemon: "bg-blue-500/15 text-blue-400",
    Trainer: "bg-amber-500/15 text-amber-400",
    Energy: "bg-emerald-500/15 text-emerald-400",
  };
  return (
    <span
      className={cn(
        "text-[10px] font-mono px-1.5 py-0.5 rounded",
        colors[category as keyof typeof colors] || "bg-surface-600 text-surface-300",
      )}
    >
      {category}
    </span>
  );
}

export function CardsClient({
  cards,
  format,
  dateRange,
}: {
  cards: CardSummary[];
  format: string;
  dateRange: { start: string; end: string };
}) {
  const [category, setCategory] = useState<CategoryFilter>("All");

  const filteredCards = useMemo(() => {
    if (category === "All") return cards;
    return cards.filter((c) => c.category === category);
  }, [cards, category]);

  const categories: CategoryFilter[] = ["All", "Pokemon", "Trainer", "Energy"];

  const columns = [
    {
      key: "card_name",
      header: "Card",
      render: (row: CardSummary) => (
        <Link
          href={`/${format}/cards/${row.card_slug}`}
          className="text-sm text-slate-200 hover:text-accent transition-colors"
        >
          {row.card_name}
        </Link>
      ),
      sortValue: (row: CardSummary) => row.card_name,
    },
    {
      key: "category",
      header: "Type",
      render: (row: CardSummary) => <CategoryBadge category={row.category} />,
      sortValue: (row: CardSummary) => row.category,
      hideOnMobile: true,
    },
    {
      key: "usage_pct",
      header: "Usage %",
      render: (row: CardSummary) => (
        <span className="font-mono text-sm text-slate-300 tabular-nums">
          {formatPct(row.usage_pct)}
        </span>
      ),
      sortValue: (row: CardSummary) => row.usage_pct,
      align: "right" as const,
    },
    {
      key: "avg_copies",
      header: "Avg Copies",
      render: (row: CardSummary) => (
        <span className="font-mono text-sm text-slate-300 tabular-nums">
          {row.avg_copies.toFixed(1)}
        </span>
      ),
      sortValue: (row: CardSummary) => row.avg_copies,
      align: "right" as const,
      hideOnMobile: true,
    },
    {
      key: "top_archetype",
      header: "Top Archetype",
      render: (row: CardSummary) => (
        <span className="text-xs text-surface-300 truncate max-w-[150px] inline-block">
          {row.top_archetype || "-"}
        </span>
      ),
      sortValue: (row: CardSummary) => row.top_archetype || "",
      hideOnMobile: true,
    },
    {
      key: "trend",
      header: "Trend",
      render: (row: CardSummary) => <TrendIcon direction={row.trend_direction} />,
      sortValue: (row: CardSummary) =>
        row.trend_direction === "surging" ? 2 : row.trend_direction === "declining" ? 0 : 1,
      align: "right" as const,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold text-slate-100">Cards</h1>
          <p className="text-sm text-surface-300 mt-1">
            {cards.length} cards tracked across all archetypes{" "}
            <Link href="/guide#cards" className="text-accent hover:text-accent/80 transition-colors">
              How this works &rarr;
            </Link>
          </p>
        </div>
      </div>

      {/* Category filter tabs */}
      <div className="flex gap-1">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setCategory(cat)}
            className={cn(
              "px-3 py-1.5 text-sm rounded-md transition-colors",
              category === cat
                ? "bg-surface-600 text-slate-100"
                : "text-surface-300 hover:text-slate-200 hover:bg-surface-700",
            )}
          >
            {cat}
          </button>
        ))}
      </div>

      <DataTable
        data={filteredCards}
        columns={columns}
        searchKey={(row) => row.card_name}
        searchPlaceholder="Search cards..."
        pageSizes={[25, 50, 100]}
        defaultPageSize={10}
      />
    </div>
  );
}
