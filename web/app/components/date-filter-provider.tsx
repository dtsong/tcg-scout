"use client";

import { createContext, useContext, useState, useCallback, useMemo } from "react";
import type { TimeWindow, MetaData } from "@/app/lib/types";

interface DateFilterState {
  activeWindow: TimeWindow;
  customRange?: { start: string; end: string };
  setWindow: (window: TimeWindow, customRange?: { start: string; end: string }) => void;
  /** Resolved data suffix for fetching windowed JSON files */
  dataSuffix: string;
}

const DateFilterContext = createContext<DateFilterState | null>(null);

export function DateFilterProvider({
  children,
  initialDateRange,
}: {
  children: React.ReactNode;
  initialDateRange: { start: string; end: string };
}) {
  const [activeWindow, setActiveWindow] = useState<TimeWindow>("all");
  const [customRange, setCustomRange] = useState<{ start: string; end: string } | undefined>();

  const setWindow = useCallback(
    (window: TimeWindow, range?: { start: string; end: string }) => {
      setActiveWindow(window);
      if (window === "custom" && range) {
        setCustomRange(range);
      }
    },
    [],
  );

  const dataSuffix = useMemo(() => {
    if (activeWindow === "all") return "";
    if (activeWindow === "7d") return "-7d";
    if (activeWindow === "30d") return "-30d";
    // Custom ranges use the full dataset and filter client-side
    return "";
  }, [activeWindow]);

  const value = useMemo(
    () => ({ activeWindow, customRange, setWindow, dataSuffix }),
    [activeWindow, customRange, setWindow, dataSuffix],
  );

  return (
    <DateFilterContext.Provider value={value}>
      {children}
    </DateFilterContext.Provider>
  );
}

export function useDateFilter() {
  const ctx = useContext(DateFilterContext);
  if (!ctx) throw new Error("useDateFilter must be used within DateFilterProvider");
  return ctx;
}

/**
 * Fetch windowed data from static JSON files.
 * Falls back to the base file if the windowed variant doesn't exist.
 */
export async function fetchWindowedData<T>(
  format: string,
  filename: string,
  suffix: string,
): Promise<T | null> {
  if (!suffix) return null; // No suffix means use default (SSR) data

  // Insert suffix before .json: "meta.json" -> "meta-7d.json"
  const base = filename.replace(".json", "");
  const windowedPath = `/data/${format}/${base}${suffix}.json`;

  try {
    const res = await fetch(windowedPath);
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error(`[date-filter] Failed to fetch ${windowedPath}:`, err);
    return null;
  }
}

/**
 * Filter data by custom date range client-side.
 * Used when the user picks a custom range and we need to filter
 * items that have a date field.
 */
export function filterByDateRange<T extends Record<string, unknown>>(
  items: T[],
  dateField: keyof T,
  range: { start: string; end: string },
): T[] {
  return items.filter((item) => {
    const date = item[dateField] as string;
    if (!date) return true;
    return date >= range.start && date <= range.end;
  });
}
