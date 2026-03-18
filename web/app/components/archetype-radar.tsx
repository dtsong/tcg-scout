"use client";

import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from "recharts";
import type { ArchetypeRadar as ArchetypeRadarData } from "@/app/lib/types";

interface ArchetypeRadarProps {
  radar: ArchetypeRadarData;
}

const AXES: { key: keyof ArchetypeRadarData; label: string }[] = [
  { key: "meta_share", label: "Meta Share" },
  { key: "weighted_share", label: "Weighted" },
  { key: "consistency", label: "Consistency" },
  { key: "ceiling", label: "Ceiling" },
  { key: "popularity", label: "Popularity" },
  { key: "core_density", label: "Core Density" },
];

export function ArchetypeRadar({ radar }: ArchetypeRadarProps) {
  const data = AXES.map(({ key, label }) => ({
    axis: label,
    value: radar[key],
  }));

  return (
    <section className="bg-surface-800 border border-surface-600 rounded-lg p-5">
      <h2 className="font-display text-lg font-semibold text-slate-100 mb-3">
        Performance Profile
      </h2>
      <ResponsiveContainer width="100%" height={280}>
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="70%">
          <PolarGrid stroke="#1c2130" />
          <PolarAngleAxis
            dataKey="axis"
            tick={{ fill: "#6b7280", fontSize: 11 }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={false}
            axisLine={false}
          />
          <Radar
            dataKey="value"
            stroke="#f59e0b"
            fill="#f59e0b"
            fillOpacity={0.25}
            strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </section>
  );
}
