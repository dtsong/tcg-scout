"use client";

import { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { TechEvolutionCard } from "@/app/lib/types";

const COLORS = [
  "#f59e0b", "#14b8a6", "#8b5cf6", "#ef4444",
  "#3b82f6", "#ec4899", "#10b981", "#f97316",
];

export function TechEvolutionChart({
  weeks,
  cards,
}: {
  weeks: string[];
  cards: TechEvolutionCard[];
}) {
  // Show top 8 cards by absolute delta
  const topCards = cards.slice(0, 8);
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  // Build chart data: one object per week
  const data = weeks.map((week, i) => {
    const point: Record<string, string | number> = {
      week,
      label: (() => {
        const d = new Date(week);
        return `${d.getMonth() + 1}/${d.getDate()}`;
      })(),
    };
    for (const card of topCards) {
      point[card.card_name] = card.timeline[i] ?? 0;
    }
    return point;
  });

  function toggleCard(name: string) {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  }

  if (topCards.length === 0) return null;

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-3">
        {topCards.map((card, i) => {
          const isHidden = hidden.has(card.card_name);
          return (
            <button
              key={card.card_name}
              onClick={() => toggleCard(card.card_name)}
              className={`text-xs px-2 py-1 rounded-full border transition-colors ${
                isHidden
                  ? "border-surface-600 text-surface-500 bg-transparent"
                  : "border-transparent text-slate-200"
              }`}
              style={!isHidden ? { backgroundColor: `${COLORS[i % COLORS.length]}20` } : undefined}
            >
              <span
                className="inline-block w-2 h-2 rounded-full mr-1.5"
                style={{ backgroundColor: isHidden ? "#475569" : COLORS[i % COLORS.length] }}
              />
              {card.card_name}
              <span className="ml-1 text-surface-400">
                {card.total_delta > 0 ? "+" : ""}
                {card.total_delta.toFixed(0)}%
              </span>
            </button>
          );
        })}
      </div>
      <div className="bg-surface-800 border border-surface-600 rounded-md p-4">
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
              <XAxis
                dataKey="label"
                tick={{ fill: "#64748b", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#64748b", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `${v}%`}
                width={36}
                domain={[0, 100]}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1e293b",
                  border: "1px solid #334155",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
                labelFormatter={(_, payload) => {
                  if (payload?.[0]?.payload?.week) {
                    return `Week of ${payload[0].payload.week}`;
                  }
                  return "";
                }}
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                formatter={(value: any, name: any) => [`${Number(value).toFixed(1)}%`, name]}
              />
              <Legend content={() => null} />
              {topCards.map((card, i) => (
                <Line
                  key={card.card_name}
                  type="monotone"
                  dataKey={card.card_name}
                  stroke={COLORS[i % COLORS.length]}
                  strokeWidth={2}
                  dot={false}
                  hide={hidden.has(card.card_name)}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
