"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { CalendarDays, ChevronDown } from "lucide-react";
import { cn } from "@/app/lib/utils";
import type { TimeWindow } from "@/app/lib/types";

const PRESET_WINDOWS: { key: TimeWindow; label: string }[] = [
  { key: "all", label: "All Time" },
  { key: "30d", label: "Last 30d" },
  { key: "7d", label: "Last 7d" },
];

interface DateFilterProps {
  activeWindow: TimeWindow;
  onWindowChange: (window: TimeWindow, customRange?: { start: string; end: string }) => void;
  dateRange: { start: string; end: string };
  customRange?: { start: string; end: string };
  enableCustom?: boolean;
}

export function DateFilter({
  activeWindow,
  onWindowChange,
  dateRange,
  customRange,
  enableCustom = false,
}: DateFilterProps) {
  const [showCustom, setShowCustom] = useState(activeWindow === "custom");
  const [customStart, setCustomStart] = useState(customRange?.start || dateRange.start);
  const [customEnd, setCustomEnd] = useState(customRange?.end || dateRange.end);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (activeWindow !== "custom") {
      setShowCustom(false);
    }
  }, [activeWindow]);

  const handlePresetClick = useCallback(
    (key: TimeWindow) => {
      if (key === activeWindow) return;
      setShowCustom(false);
      onWindowChange(key);
    },
    [activeWindow, onWindowChange],
  );

  const handleCustomToggle = useCallback(() => {
    if (activeWindow === "custom") {
      setShowCustom((prev) => !prev);
    } else {
      setShowCustom(true);
      onWindowChange("custom", { start: customStart, end: customEnd });
    }
  }, [activeWindow, onWindowChange, customStart, customEnd]);

  const handleApplyCustom = useCallback(() => {
    onWindowChange("custom", { start: customStart, end: customEnd });
  }, [onWindowChange, customStart, customEnd]);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-1 text-xs text-surface-300 mr-1">
          <CalendarDays className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Window</span>
        </div>

        <div className="flex items-center bg-surface-700/50 rounded-md p-0.5 border border-surface-600">
          {PRESET_WINDOWS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => handlePresetClick(key)}
              className={cn(
                "px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-150",
                activeWindow === key
                  ? "bg-accent/15 text-accent shadow-sm shadow-accent/10 border border-accent/25"
                  : "text-surface-300 hover:text-slate-200 border border-transparent",
              )}
            >
              {label}
            </button>
          ))}

          {enableCustom && (
            <button
              onClick={handleCustomToggle}
              className={cn(
                "px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-150 flex items-center gap-1",
                activeWindow === "custom"
                  ? "bg-accent/15 text-accent shadow-sm shadow-accent/10 border border-accent/25"
                  : "text-surface-300 hover:text-slate-200 border border-transparent",
              )}
            >
              Custom
              <ChevronDown
                className={cn(
                  "w-3 h-3 transition-transform duration-200",
                  showCustom && "rotate-180",
                )}
              />
            </button>
          )}
        </div>

        {activeWindow !== "all" && (
          <span className="text-xs text-surface-400 font-mono tabular-nums">
            {activeWindow === "custom"
              ? `${customStart} to ${customEnd}`
              : activeWindow === "7d"
                ? "Last 7 days"
                : "Last 30 days"}
          </span>
        )}
      </div>

      {enableCustom && (
        <div
          ref={panelRef}
          className={cn(
            "grid transition-all duration-200 ease-out",
            showCustom
              ? "grid-rows-[1fr] opacity-100"
              : "grid-rows-[0fr] opacity-0",
          )}
        >
          <div className="overflow-hidden">
            <div className="flex items-end gap-3 pt-1 pb-0.5">
              <div className="flex flex-col gap-1">
                <label className="text-xs text-surface-400">From</label>
                <input
                  type="date"
                  value={customStart}
                  min={dateRange.start}
                  max={customEnd}
                  onChange={(e) => setCustomStart(e.target.value)}
                  className="bg-surface-700 border border-surface-500 rounded-md px-2.5 py-1.5 text-xs text-slate-200 font-mono
                    focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20
                    [color-scheme:dark] transition-colors"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-surface-400">To</label>
                <input
                  type="date"
                  value={customEnd}
                  min={customStart}
                  max={dateRange.end}
                  onChange={(e) => setCustomEnd(e.target.value)}
                  className="bg-surface-700 border border-surface-500 rounded-md px-2.5 py-1.5 text-xs text-slate-200 font-mono
                    focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20
                    [color-scheme:dark] transition-colors"
                />
              </div>
              <button
                onClick={handleApplyCustom}
                className="px-3 py-1.5 text-xs font-medium rounded-md bg-accent/15 text-accent
                  border border-accent/25 hover:bg-accent/25 transition-colors"
              >
                Apply
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
