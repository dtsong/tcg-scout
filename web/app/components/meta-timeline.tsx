"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { TimelineData } from "@/app/lib/types";

interface MetaTimelineProps {
  data: TimelineData;
}

const PALETTE = [
  "#f59e0b", // amber
  "#14b8a6", // teal
  "#3b82f6", // blue
  "#a855f7", // purple
  "#ef4444", // red
  "#22c55e", // green
  "#ec4899", // pink
  "#f97316", // orange
  "#06b6d4", // cyan
  "#8b5cf6", // violet
  "#eab308", // yellow
  "#64748b", // slate
];

function formatWeekLabel(dateStr: string): string {
  const date = new Date(dateStr + "T00:00:00");
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

interface TooltipPayloadEntry {
  name: string;
  value: number;
  color: string;
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
}) {
  if (!active || !payload || !label) return null;

  const sorted = [...payload]
    .filter((entry) => entry.value > 0)
    .sort((a, b) => b.value - a.value);

  return (
    <div className="bg-surface-800 border border-surface-600 rounded-md p-3 shadow-lg max-h-64 overflow-y-auto">
      <p className="text-xs font-semibold text-slate-200 mb-2">
        {formatWeekLabel(label)}
      </p>
      <div className="space-y-1">
        {sorted.map((entry) => (
          <div
            key={entry.name}
            className="flex items-center justify-between gap-4 text-xs"
          >
            <div className="flex items-center gap-1.5 min-w-0">
              <span
                className="w-2 h-2 rounded-full shrink-0"
                style={{ backgroundColor: entry.color }}
              />
              <span className="text-slate-300 truncate">{entry.name}</span>
            </div>
            <span className="font-mono text-surface-300 tabular-nums shrink-0">
              {entry.value.toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function MetaTimeline({ data }: MetaTimelineProps) {
  const chartData = data.weeks.map((w) => ({
    week: w.week,
    ...w.archetypes,
  }));

  const archetypes = data.archetype_order;

  return (
    <section className="bg-surface-800 border border-surface-600 rounded-md p-5">
      <h2 className="font-display text-lg font-semibold text-slate-100 mb-3">
        Meta Timeline
      </h2>
      <ResponsiveContainer width="100%" height={350}>
        <AreaChart data={chartData}>
          <XAxis
            dataKey="week"
            tickFormatter={formatWeekLabel}
            tick={{ fill: "#6b7280", fontSize: 11 }}
            axisLine={{ stroke: "#1c2130" }}
            tickLine={{ stroke: "#1c2130" }}
          />
          <YAxis
            domain={[0, 100]}
            tickFormatter={(v: number) => `${v}%`}
            tick={{ fill: "#6b7280", fontSize: 11 }}
            axisLine={{ stroke: "#1c2130" }}
            tickLine={{ stroke: "#1c2130" }}
            width={40}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{
              fontSize: 11,
              paddingTop: 8,
              maxHeight: 60,
              overflowY: "auto",
            }}
          />
          {archetypes.map((archetype, i) => (
            <Area
              key={archetype}
              type="monotone"
              dataKey={archetype}
              stackId="1"
              stroke={PALETTE[i % PALETTE.length]}
              fill={PALETTE[i % PALETTE.length]}
              fillOpacity={0.8}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </section>
  );
}
