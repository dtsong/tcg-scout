"use client";

import { Fragment, useState } from "react";
import { cn } from "@/app/lib/utils";
import type { MatchupMatrixData } from "@/app/lib/types";

function cellColor(value: number): string {
  if (value === 0) return "";
  if (value >= 3) return "bg-emerald-500/40";
  if (value >= 1.5) return "bg-emerald-500/25";
  if (value >= 0.5) return "bg-emerald-500/10";
  if (value <= -3) return "bg-red-500/40";
  if (value <= -1.5) return "bg-red-500/25";
  if (value <= -0.5) return "bg-red-500/10";
  return "";
}

function cellText(value: number, sampleSize: number): string {
  if (sampleSize < 10) return "";
  if (value === 0) return "-";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}`;
}

export function MatchupHeatMatrix({ data }: { data: MatchupMatrixData }) {
  const [hovered, setHovered] = useState<{ row: number; col: number } | null>(null);
  const n = data.archetypes.length;

  if (n === 0) return null;

  // Truncate long archetype names
  const shortName = (name: string) => {
    if (name.length <= 14) return name;
    return name.slice(0, 12) + "...";
  };

  return (
    <div className="overflow-x-auto">
      <div
        className="inline-grid"
        style={{ gridTemplateColumns: `120px repeat(${n}, 40px)` }}
      >
        {/* Header row */}
        <div />
        {data.archetypes.map((name, j) => (
          <div
            key={`h-${j}`}
            className="flex items-end justify-center pb-1"
            title={name}
          >
            <span className="text-[8px] text-surface-400 writing-vertical"
              style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
            >
              {shortName(name)}
            </span>
          </div>
        ))}

        {/* Data rows */}
        {data.archetypes.map((rowName, i) => (
          <Fragment key={i}>
            <div
              className="flex items-center pr-2 h-10"
            >
              <span
                className="text-[10px] text-surface-300 truncate max-w-[110px]"
                title={rowName}
              >
                {shortName(rowName)}
              </span>
            </div>
            {data.archetypes.map((_, j) => {
              const value = data.matrix[i][j];
              const samples = data.sample_sizes[i][j];
              const isDiag = i === j;
              const isHovered = hovered?.row === i || hovered?.col === j;
              const text = isDiag ? "-" : cellText(value, samples);
              return (
                <div
                  key={`cell-${i}-${j}`}
                  className={cn(
                    "h-10 w-10 flex items-center justify-center text-[9px] font-mono tabular-nums transition-opacity",
                    isDiag ? "bg-surface-600" : cellColor(value),
                    isHovered && !isDiag ? "ring-1 ring-surface-400/40" : "",
                    isDiag
                      ? "text-surface-400"
                      : value > 0
                        ? "text-emerald-300"
                        : value < 0
                          ? "text-red-300"
                          : "text-surface-500",
                  )}
                  onMouseEnter={() => setHovered({ row: i, col: j })}
                  onMouseLeave={() => setHovered(null)}
                  title={
                    isDiag
                      ? rowName
                      : `${rowName} vs ${data.archetypes[j]}: ${value > 0 ? "+" : ""}${value.toFixed(1)} advantage (${samples} events)`
                  }
                >
                  {text}
                </div>
              );
            })}
          </Fragment>
        ))}
      </div>

      {hovered && hovered.row !== hovered.col && (
        <div className="mt-2 text-xs text-surface-400">
          {data.archetypes[hovered.row]} vs {data.archetypes[hovered.col]}:{" "}
          <span className={cn(
            "font-mono",
            data.matrix[hovered.row][hovered.col] > 0 ? "text-emerald-300" : data.matrix[hovered.row][hovered.col] < 0 ? "text-red-300" : "text-slate-300"
          )}>
            {data.matrix[hovered.row][hovered.col] > 0 ? "+" : ""}
            {data.matrix[hovered.row][hovered.col].toFixed(1)}
          </span>{" "}
          standing advantage ({data.sample_sizes[hovered.row][hovered.col]} events)
        </div>
      )}
    </div>
  );
}
