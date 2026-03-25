"use client";

import { Fragment, useState } from "react";
import { cn } from "@/app/lib/utils";
import type { MatchupMatrixData } from "@/app/lib/types";
import { Tooltip } from "@/app/components/tooltip";

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
            className={cn(
              "flex items-end justify-center pb-1 transition-opacity duration-[var(--duration-fast)]",
              hovered !== null && hovered.col !== j ? "opacity-30" : "opacity-100",
            )}
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
              className={cn(
                "flex items-center pr-2 h-10 transition-opacity duration-[var(--duration-fast)]",
                hovered !== null && hovered.row !== i ? "opacity-30" : "opacity-100",
              )}
            >
              <span
                className="text-[10px] text-surface-300 truncate max-w-[110px]"
                title={rowName}
              >
                {shortName(rowName)}
              </span>
            </div>
            {data.archetypes.map((colName, j) => {
              const value = data.matrix[i][j];
              const samples = data.sample_sizes[i][j];
              const isDiag = i === j;
              const isInCrosshair = hovered?.row === i || hovered?.col === j;
              const isDimmed = hovered !== null && !isInCrosshair;
              const isTarget = hovered?.row === i && hovered?.col === j;
              const text = isDiag ? "-" : cellText(value, samples);
              const cell = (
                <div
                  className={cn(
                    "h-10 w-10 flex items-center justify-center text-[9px] font-mono tabular-nums",
                    "transition-opacity duration-[var(--duration-fast)]",
                    isDiag ? "bg-surface-600" : cellColor(value),
                    isTarget && !isDiag ? "ring-1 ring-terminal/60" : "",
                    isInCrosshair && !isDiag && !isTarget ? "ring-1 ring-surface-400/30" : "",
                    isDimmed ? "opacity-30" : "opacity-100",
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
                >
                  {text}
                </div>
              );
              if (isDiag) return <Fragment key={`cell-${i}-${j}`}>{cell}</Fragment>;
              return (
                <Tooltip
                  key={`cell-${i}-${j}`}
                  content={
                    samples < 10 ? (
                      `Not enough data (${samples} tournaments, minimum 10 required)`
                    ) : (
                      <>
                        <strong>{rowName}</strong> vs <strong>{colName}</strong>
                        {": "}
                        {value > 0 ? "+" : ""}{value.toFixed(1)} standing advantage ({samples} tournaments)
                      </>
                    )
                  }
                >
                  {cell}
                </Tooltip>
              );
            })}
          </Fragment>
        ))}
      </div>

    </div>
  );
}
