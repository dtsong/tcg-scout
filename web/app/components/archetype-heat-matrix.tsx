"use client";

import { useMemo, useState } from "react";
import { cn } from "@/app/lib/utils";
import { SpriteRow } from "@/app/components/sprite-row";

interface MatrixEntry {
  archetype: string;
  slug: string;
  sprite_filenames?: string[];
  weighted_share: number;
}

interface MatrixData {
  archetypes: MatrixEntry[];
  matrix: number[][]; // similarity values 0-1
}

export function ArchetypeHeatMatrix({
  data,
  format,
}: {
  data: MatrixData;
  format: string;
}) {
  const [hovered, setHovered] = useState<{ row: number; col: number } | null>(null);
  const n = data.archetypes.length;

  const maxVal = useMemo(() => {
    let max = 0;
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        if (i !== j && data.matrix[i][j] > max) max = data.matrix[i][j];
      }
    }
    return max || 1;
  }, [data, n]);

  function cellColor(value: number, isDiag: boolean): string {
    if (isDiag) return "bg-surface-600";
    const intensity = Math.min(value / maxVal, 1);
    if (intensity < 0.2) return "bg-surface-700/50";
    if (intensity < 0.4) return "bg-blue-900/30";
    if (intensity < 0.6) return "bg-blue-800/40";
    if (intensity < 0.8) return "bg-blue-600/40";
    return "bg-blue-500/50";
  }

  if (n === 0) return null;

  return (
    <div className="overflow-x-auto">
      <div className="inline-grid" style={{ gridTemplateColumns: `120px repeat(${n}, 36px)` }}>
        {/* Header row */}
        <div /> {/* empty corner */}
        {data.archetypes.map((arch, j) => (
          <div
            key={`h-${j}`}
            className="flex items-end justify-center pb-1"
            title={arch.archetype}
          >
            <SpriteRow filenames={arch.sprite_filenames?.slice(0, 1) ?? []} size={16} />
          </div>
        ))}

        {/* Data rows */}
        {data.archetypes.map((rowArch, i) => (
          <>
            <div
              key={`label-${i}`}
              className="flex items-center gap-1.5 pr-2 h-9"
            >
              <SpriteRow filenames={rowArch.sprite_filenames?.slice(0, 1) ?? []} size={16} />
              <a
                href={`/${format}/archetypes/${rowArch.slug}`}
                className="text-[10px] text-surface-300 hover:text-accent truncate max-w-[80px] transition-colors"
                title={rowArch.archetype}
              >
                {rowArch.archetype}
              </a>
            </div>
            {data.archetypes.map((_, j) => {
              const value = data.matrix[i][j];
              const isDiag = i === j;
              const isHovered = hovered?.row === i || hovered?.col === j;
              return (
                <div
                  key={`cell-${i}-${j}`}
                  className={cn(
                    "h-9 w-9 flex items-center justify-center text-[9px] font-mono tabular-nums transition-opacity",
                    cellColor(value, isDiag),
                    isHovered && !isDiag ? "ring-1 ring-blue-400/40" : "",
                    isDiag ? "text-surface-400" : value > 0 ? "text-slate-300" : "text-surface-500",
                  )}
                  onMouseEnter={() => setHovered({ row: i, col: j })}
                  onMouseLeave={() => setHovered(null)}
                  title={
                    isDiag
                      ? rowArch.archetype
                      : `${rowArch.archetype} & ${data.archetypes[j].archetype}: ${(value * 100).toFixed(0)}% shared`
                  }
                >
                  {isDiag ? "-" : value > 0 ? `${(value * 100).toFixed(0)}` : ""}
                </div>
              );
            })}
          </>
        ))}
      </div>

      {hovered && hovered.row !== hovered.col && (
        <div className="mt-2 text-xs text-surface-400">
          {data.archetypes[hovered.row].archetype} &amp; {data.archetypes[hovered.col].archetype}:{" "}
          <span className="text-slate-300 font-mono">
            {(data.matrix[hovered.row][hovered.col] * 100).toFixed(1)}%
          </span>{" "}
          shared cards
        </div>
      )}
    </div>
  );
}
