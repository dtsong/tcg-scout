"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { ArchetypeSummary, Tier } from "@/app/lib/types";

const tierColors: Record<Tier, string> = {
  S: "#f59e0b",
  A: "#14b8a6",
  B: "#3b82f6",
  C: "#64748b",
  Rogue: "#a855f7",
};

export function MetaBarChart({ data }: { data: ArchetypeSummary[] }) {
  const chartData = data.slice(0, 20).map((a) => ({
    name: a.archetype.length > 20 ? a.archetype.slice(0, 18) + "..." : a.archetype,
    share: a.meta_share,
    tier: a.tier,
  }));

  return (
    <ResponsiveContainer width="100%" height={500}>
      <BarChart data={chartData} layout="vertical" margin={{ left: 140, right: 20 }}>
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
          width={140}
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
          formatter={(value: any) => [`${Number(value).toFixed(1)}%`, "Meta Share"]}
          cursor={{ fill: "rgba(255,255,255,0.03)" }}
        />
        <Bar dataKey="share" radius={[0, 4, 4, 0]} barSize={18}>
          {chartData.map((entry, i) => (
            <Cell key={i} fill={tierColors[entry.tier as Tier]} fillOpacity={0.8} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
