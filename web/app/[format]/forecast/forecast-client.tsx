"use client";

import { useState, useMemo, Fragment } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Sparkles,
  ChevronDown,
  ChevronRight,
  ArrowUpDown,
} from "lucide-react";
import type { TechForecast, TechForecastCard } from "@/app/lib/types";

type SortKey =
  | "card_name"
  | "current_adoption_pct"
  | "current_avg_copies"
  | "trend_delta";
type SortDir = "asc" | "desc";

function TrendIcon({
  direction,
}: {
  direction: TechForecastCard["trend_direction"];
}) {
  switch (direction) {
    case "rising":
      return <TrendingUp className="w-4 h-4 text-signal-up" />;
    case "falling":
      return <TrendingDown className="w-4 h-4 text-signal-down" />;
    case "new":
      return <Sparkles className="w-4 h-4 text-blue-400" />;
    case "stable":
    default:
      return <Minus className="w-4 h-4 text-surface-300" />;
  }
}

function trendColor(direction: TechForecastCard["trend_direction"]): string {
  switch (direction) {
    case "rising":
      return "text-signal-up";
    case "falling":
      return "text-signal-down";
    case "new":
      return "text-blue-400";
    case "stable":
    default:
      return "text-surface-300";
  }
}

function MiniSparkline({ data }: { data: TechForecastCard["weekly_data"] }) {
  const recent = data.slice(-8);
  if (recent.length < 2) return null;

  return (
    <div className="w-[120px] h-[32px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={recent}>
          <Line
            type="monotone"
            dataKey="adoption_pct"
            stroke="#60a5fa"
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function CardDetailPanel({ card }: { card: TechForecastCard }) {
  return (
    <div className="bg-surface-900/50 border-t border-surface-600 px-4 py-5 sm:px-6 space-y-6">
      {/* Weekly adoption chart */}
      <div>
        <h3 className="font-display text-sm font-semibold text-slate-200 mb-3">
          Weekly Adoption
        </h3>
        <div className="h-[220px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={card.weekly_data}>
              <XAxis
                dataKey="week"
                tick={{ fill: "#6b7280", fontSize: 11 }}
                axisLine={{ stroke: "#2a3040" }}
                tickLine={false}
                tickFormatter={(v: string) => {
                  const d = new Date(v);
                  return `${d.getMonth() + 1}/${d.getDate()}`;
                }}
              />
              <YAxis
                tickFormatter={(v: number) => `${v}%`}
                tick={{ fill: "#6b7280", fontSize: 11 }}
                axisLine={{ stroke: "#2a3040" }}
                tickLine={false}
                width={45}
              />
              <Tooltip
                wrapperStyle={{ outline: "none" }}
                contentStyle={{
                  backgroundColor: "#151921",
                  border: "1px solid #2a3040",
                  borderRadius: "6px",
                  fontSize: "13px",
                }}
                labelStyle={{ color: "#e2e8f0" }}
                itemStyle={{ color: "#94a3b8" }}
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                formatter={(value: any) => [
                  `${Number(value).toFixed(1)}%`,
                  "Adoption",
                ]}
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                labelFormatter={(label: any) => {
                  const d = new Date(String(label));
                  return d.toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                  });
                }}
                cursor={{ stroke: "rgba(255,255,255,0.1)" }}
              />
              <Line
                type="monotone"
                dataKey="adoption_pct"
                stroke="#60a5fa"
                strokeWidth={2}
                dot={{ fill: "#60a5fa", r: 3 }}
                activeDot={{ r: 5, fill: "#93c5fd" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Top archetypes */}
      {card.top_archetypes.length > 0 && (
        <div>
          <h3 className="font-display text-sm font-semibold text-slate-200 mb-3">
            Top Archetypes Using This Card
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-600 text-xs text-surface-300 uppercase tracking-wider">
                  <th className="text-left px-4 py-2">Archetype</th>
                  <th className="text-right px-4 py-2">Inclusion %</th>
                  <th className="text-right px-4 py-2">Avg Copies</th>
                </tr>
              </thead>
              <tbody>
                {card.top_archetypes.map((a) => (
                  <tr
                    key={a.archetype}
                    className="border-b border-surface-700 hover:bg-surface-700/50 transition-colors"
                  >
                    <td className="px-4 py-2 text-slate-200 text-sm">
                      {a.archetype}
                    </td>
                    <td className="px-4 py-2 text-right font-mono tabular-nums text-surface-300 text-sm">
                      {a.inclusion_pct.toFixed(1)}%
                    </td>
                    <td className="px-4 py-2 text-right font-mono tabular-nums text-surface-300 text-sm">
                      {a.avg_copies.toFixed(1)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function SortableHeader({
  label,
  sortKey,
  currentKey,
  currentDir,
  onSort,
  align = "left",
}: {
  label: string;
  sortKey: SortKey;
  currentKey: SortKey;
  currentDir: SortDir;
  onSort: (key: SortKey) => void;
  align?: "left" | "right";
}) {
  const active = currentKey === sortKey;
  return (
    <th
      className={`px-4 py-3 cursor-pointer select-none hover:text-slate-200 transition-colors ${
        align === "right" ? "text-right" : "text-left"
      }`}
      onClick={() => onSort(sortKey)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {active ? (
          <ArrowUpDown className="w-3 h-3 text-accent" />
        ) : (
          <ArrowUpDown className="w-3 h-3 opacity-30" />
        )}
        {active && (
          <span className="text-[10px] text-accent">
            {currentDir === "asc" ? "ASC" : "DESC"}
          </span>
        )}
      </span>
    </th>
  );
}

export function ForecastClient({
  forecast,
}: {
  forecast: TechForecast;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("trend_delta");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [expandedCard, setExpandedCard] = useState<string | null>(null);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "card_name" ? "asc" : "desc");
    }
  };

  const sorted = useMemo(() => {
    const cards = [...forecast.cards];
    cards.sort((a, b) => {
      let cmp: number;
      switch (sortKey) {
        case "card_name":
          cmp = a.card_name.localeCompare(b.card_name);
          break;
        case "current_adoption_pct":
          cmp = a.current_adoption_pct - b.current_adoption_pct;
          break;
        case "current_avg_copies":
          cmp = a.current_avg_copies - b.current_avg_copies;
          break;
        case "trend_delta":
          cmp = Math.abs(a.trend_delta) - Math.abs(b.trend_delta);
          break;
        default:
          cmp = 0;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return cards;
  }, [forecast.cards, sortKey, sortDir]);

  const toggleExpand = (cardName: string) => {
    setExpandedCard((prev) => (prev === cardName ? null : cardName));
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-2xl font-bold text-slate-100">
          Meta Card Forecast
        </h1>
        <p className="text-sm text-surface-300 mt-1">
          Tracking {forecast.cards.length} tech cards across weekly snapshots
        </p>
      </div>

      {/* Card table */}
      <div className="bg-surface-800 border border-surface-600 rounded-md overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-600 text-xs text-surface-300 uppercase tracking-wider">
                <th className="w-8 px-2 py-3" />
                <SortableHeader
                  label="Card"
                  sortKey="card_name"
                  currentKey={sortKey}
                  currentDir={sortDir}
                  onSort={handleSort}
                  align="left"
                />
                <SortableHeader
                  label="Adoption %"
                  sortKey="current_adoption_pct"
                  currentKey={sortKey}
                  currentDir={sortDir}
                  onSort={handleSort}
                  align="right"
                />
                <SortableHeader
                  label="Avg Copies"
                  sortKey="current_avg_copies"
                  currentKey={sortKey}
                  currentDir={sortDir}
                  onSort={handleSort}
                  align="right"
                />
                <SortableHeader
                  label="Trend"
                  sortKey="trend_delta"
                  currentKey={sortKey}
                  currentDir={sortDir}
                  onSort={handleSort}
                  align="right"
                />
                <th className="px-4 py-3 text-right">Sparkline</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((card, i) => {
                const isExpanded = expandedCard === card.card_name;
                return (
                  <Fragment key={card.card_name}>
                    <tr
                      className="border-b border-surface-700 hover:bg-surface-700/50 transition-colors cursor-pointer animate-row-reveal"
                      style={{ animationDelay: `${i * 20}ms` }}
                      onClick={() => toggleExpand(card.card_name)}
                    >
                      <td className="px-2 py-3 text-surface-400">
                        {isExpanded ? (
                          <ChevronDown className="w-4 h-4" />
                        ) : (
                          <ChevronRight className="w-4 h-4" />
                        )}
                      </td>
                      <td className="px-4 py-3 text-slate-200">
                        {card.card_name}
                      </td>
                      <td className="px-4 py-3 text-right font-mono tabular-nums text-surface-300">
                        {card.current_adoption_pct.toFixed(1)}%
                      </td>
                      <td className="px-4 py-3 text-right font-mono tabular-nums text-surface-300">
                        {card.current_avg_copies.toFixed(1)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span
                          className={`inline-flex items-center gap-1 font-mono tabular-nums ${trendColor(card.trend_direction)}`}
                        >
                          <TrendIcon direction={card.trend_direction} />
                          {card.trend_delta > 0 ? "+" : ""}
                          {card.trend_delta.toFixed(1)}%
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex justify-end">
                          <MiniSparkline data={card.weekly_data} />
                        </div>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr className="border-b border-surface-700">
                        <td colSpan={6}>
                          <CardDetailPanel card={card} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
