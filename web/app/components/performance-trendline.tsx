"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

interface WeeklyShare {
  week: string;
  meta_share: number;
  deck_count: number;
}

export function PerformanceTrendline({ data }: { data: WeeklyShare[] }) {
  const avg = data.reduce((sum, d) => sum + d.meta_share, 0) / data.length;

  return (
    <section>
      <h2 className="font-display text-lg font-semibold text-slate-100 mb-1">
        Meta Share Over Time
      </h2>
      <p className="text-xs text-surface-400 mb-3">
        Weekly meta share trend (avg: {avg.toFixed(1)}%)
      </p>
      <div className="bg-surface-800 border border-surface-600 rounded-lg p-4">
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
              <defs>
                <linearGradient id="shareGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#14b8a6" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#14b8a6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="week"
                tick={{ fill: "#64748b", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => {
                  const d = new Date(v);
                  return `${d.getMonth() + 1}/${d.getDate()}`;
                }}
              />
              <YAxis
                tick={{ fill: "#64748b", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `${v}%`}
                width={36}
              />
              <ReferenceLine
                y={avg}
                stroke="#64748b"
                strokeDasharray="3 3"
                strokeWidth={1}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1e293b",
                  border: "1px solid #334155",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
                labelFormatter={(v) => `Week of ${v}`}
                formatter={(value) => [`${Number(value).toFixed(1)}%`, "Meta Share"]}
              />
              <Area
                type="monotone"
                dataKey="meta_share"
                stroke="#14b8a6"
                fill="url(#shareGradient)"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </section>
  );
}
