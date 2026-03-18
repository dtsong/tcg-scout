"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { TrendingUp, TrendingDown, Trophy } from "lucide-react";
import type { TrendsData, WinningEdgeCard } from "@/app/lib/types";

export function TrendsClient({
  trends,
  winningEdge,
}: {
  trends: TrendsData;
  winningEdge: WinningEdgeCard[];
}) {
  const chartData = (trends.surging || []).slice(0, 15).map((c) => ({
    name: c.card_name.length > 18 ? c.card_name.slice(0, 16) + "..." : c.card_name,
    early: c.early_pct,
    late: c.late_pct,
  }));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-2xl font-bold text-slate-100">
          Trends
        </h1>
        <p className="text-sm text-surface-300 mt-1">
          Usage shifts between early ({trends.early_decks} decks) and late ({trends.late_decks} decks) periods, split at {trends.midpoint}
        </p>
      </div>

      {/* Trend Chart */}
      <div className="bg-surface-800 border border-surface-600 rounded-lg p-4 sm:p-6">
        <h2 className="font-display text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-signal-up" />
          Top Surging Cards: Early vs Late Period
        </h2>
        <ResponsiveContainer width="100%" height={450}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 130, right: 20 }}>
            <XAxis
              type="number"
              tickFormatter={(v) => `${v}%`}
              tick={{ fill: "#6b7280", fontSize: 12 }}
              axisLine={{ stroke: "#2a3040" }}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fill: "#94a3b8", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              width={130}
            />
            <Tooltip
              wrapperStyle={{ outline: 'none' }}
              contentStyle={{
                backgroundColor: "#151921",
                border: "1px solid #2a3040",
                borderRadius: "6px",
                fontSize: "13px",
              }}
              labelStyle={{ color: '#e2e8f0' }}
              itemStyle={{ color: '#94a3b8' }}
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              formatter={(value: any, name: any) => [
                `${Number(value).toFixed(1)}%`,
                name === "early" ? "Early Period" : "Late Period",
              ]}
              cursor={{ fill: "rgba(255,255,255,0.03)" }}
            />
            <Legend
              formatter={(value) => (value === "early" ? "Early Period" : "Late Period")}
              wrapperStyle={{ fontSize: "12px", color: "#94a3b8" }}
            />
            <Bar dataKey="early" fill="#3b82f6" fillOpacity={0.5} radius={[0, 4, 4, 0]} barSize={14} />
            <Bar dataKey="late" fill="#22c55e" fillOpacity={0.8} radius={[0, 4, 4, 0]} barSize={14} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Surging Cards Table */}
      <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-surface-600">
          <h2 className="font-display text-sm font-semibold text-slate-200 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-signal-up" />
            Surging Cards
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-600 text-xs text-surface-300 uppercase tracking-wider">
                <th className="text-left px-4 py-3">Card</th>
                <th className="text-right px-4 py-3">Early %</th>
                <th className="text-right px-4 py-3">Late %</th>
                <th className="text-right px-4 py-3">Delta</th>
              </tr>
            </thead>
            <tbody>
              {(trends.surging || []).map((card, i) => (
                <tr
                  key={card.card_name}
                  className="border-b border-surface-700 hover:bg-surface-700/50 transition-colors animate-row-reveal"
                  style={{ animationDelay: `${i * 20}ms` }}
                >
                  <td className="px-4 py-3">
                    <div className="text-slate-200">{card.card_name}</div>
                    {card.archetypes && card.archetypes.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {card.archetypes.slice(0, 3).map((a) => (
                          <span key={a.archetype} className="text-[10px] px-1.5 py-0.5 rounded bg-surface-700 text-surface-300">
                            {a.archetype}
                            <span className={`ml-1 ${a.delta > 0 ? "text-signal-up" : a.delta < 0 ? "text-signal-down" : "text-surface-400"}`}>
                              {a.delta > 0 ? "+" : ""}{a.delta.toFixed(1)}%
                            </span>
                          </span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums text-surface-300">
                    {card.early_pct.toFixed(1)}%
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums text-surface-300">
                    {card.late_pct.toFixed(1)}%
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums">
                    <span className={card.delta > 0 ? "text-signal-up" : card.delta < 0 ? "text-signal-down" : "text-surface-400"}>
                      {card.delta > 0 ? "+" : ""}
                      {card.delta.toFixed(1)}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Declining Cards Table */}
      <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-surface-600">
          <h2 className="font-display text-sm font-semibold text-slate-200 flex items-center gap-2">
            <TrendingDown className="w-4 h-4 text-signal-down" />
            Declining Cards
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-600 text-xs text-surface-300 uppercase tracking-wider">
                <th className="text-left px-4 py-3">Card</th>
                <th className="text-right px-4 py-3">Early %</th>
                <th className="text-right px-4 py-3">Late %</th>
                <th className="text-right px-4 py-3">Delta</th>
              </tr>
            </thead>
            <tbody>
              {(trends.declining || []).map((card, i) => (
                <tr
                  key={card.card_name}
                  className="border-b border-surface-700 hover:bg-surface-700/50 transition-colors animate-row-reveal"
                  style={{ animationDelay: `${i * 20}ms` }}
                >
                  <td className="px-4 py-3">
                    <div className="text-slate-200">{card.card_name}</div>
                    {card.archetypes && card.archetypes.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {card.archetypes.slice(0, 3).map((a) => (
                          <span key={a.archetype} className="text-[10px] px-1.5 py-0.5 rounded bg-surface-700 text-surface-300">
                            {a.archetype}
                            <span className={`ml-1 ${a.delta > 0 ? "text-signal-up" : a.delta < 0 ? "text-signal-down" : "text-surface-400"}`}>
                              {a.delta > 0 ? "+" : ""}{a.delta.toFixed(1)}%
                            </span>
                          </span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums text-surface-300">
                    {card.early_pct.toFixed(1)}%
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums text-surface-300">
                    {card.late_pct.toFixed(1)}%
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums">
                    <span className="text-signal-down">
                      {card.delta.toFixed(1)}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Winning Edge */}
      <div className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-surface-600">
          <h2 className="font-display text-sm font-semibold text-slate-200 flex items-center gap-2">
            <Trophy className="w-4 h-4 text-tier-s" />
            Winning Edge: 1st Place Overrepresentation vs Field
          </h2>
          <p className="text-xs text-surface-400 mt-1">
            Cards that appear more often in winning decks than in the general field (S/A/B tiers)
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-600 text-xs text-surface-300 uppercase tracking-wider">
                <th className="text-left px-4 py-3">Card</th>
                <th className="text-right px-4 py-3">Field %</th>
                <th className="text-right px-4 py-3">Winner %</th>
                <th className="text-right px-4 py-3">Edge</th>
              </tr>
            </thead>
            <tbody>
              {winningEdge.map((card, i) => (
                <tr
                  key={card.card_name}
                  className="border-b border-surface-700 hover:bg-surface-700/50 transition-colors animate-row-reveal"
                  style={{ animationDelay: `${i * 20}ms` }}
                >
                  <td className="px-4 py-3 text-slate-200">{card.card_name}</td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums text-surface-300">
                    {card.field_pct.toFixed(1)}%
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums text-surface-300">
                    {card.win_pct.toFixed(1)}%
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums">
                    <span className={card.edge > 0 ? "text-signal-up" : "text-signal-down"}>
                      {card.edge > 0 ? "+" : ""}
                      {card.edge.toFixed(1)}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
