"use client";

import { useState, useMemo } from "react";
import { ArrowUpDown, Search } from "lucide-react";
import { cn } from "@/app/lib/utils";

interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => React.ReactNode;
  sortValue?: (row: T) => number | string;
  align?: "left" | "right";
  hideOnMobile?: boolean;
}

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  searchKey?: (row: T) => string;
  searchPlaceholder?: string;
}

export function DataTable<T>({
  data,
  columns,
  searchKey,
  searchPlaceholder = "Search...",
}: DataTableProps<T>) {
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    if (!search || !searchKey) return data;
    const q = search.toLowerCase();
    return data.filter((row) => searchKey(row).toLowerCase().includes(q));
  }, [data, search, searchKey]);

  const sorted = useMemo(() => {
    if (!sortCol) return filtered;
    const col = columns.find((c) => c.key === sortCol);
    if (!col?.sortValue) return filtered;
    const getValue = col.sortValue;
    return [...filtered].sort((a, b) => {
      const va = getValue(a);
      const vb = getValue(b);
      if (typeof va === "number" && typeof vb === "number") {
        return sortDir === "asc" ? va - vb : vb - va;
      }
      return sortDir === "asc"
        ? String(va).localeCompare(String(vb))
        : String(vb).localeCompare(String(va));
    });
  }, [filtered, sortCol, sortDir, columns]);

  function toggleSort(key: string) {
    if (sortCol === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(key);
      setSortDir("desc");
    }
  }

  return (
    <div>
      {searchKey && (
        <div className="relative mb-4">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={searchPlaceholder}
            className="w-full sm:w-72 bg-surface-700 border border-surface-600 rounded-md pl-9 pr-3 py-2 text-sm text-slate-200 placeholder-surface-400 focus:outline-none focus:border-surface-400"
          />
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-surface-600 text-xs text-surface-300 uppercase tracking-wider">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cn(
                    "px-4 py-3",
                    col.align === "right" ? "text-right" : "text-left",
                    col.hideOnMobile && "hidden sm:table-cell",
                    col.sortValue && "cursor-pointer select-none hover:text-slate-300",
                  )}
                  onClick={() => col.sortValue && toggleSort(col.key)}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.header}
                    {col.sortValue && (
                      <ArrowUpDown
                        className={cn(
                          "w-3 h-3",
                          sortCol === col.key ? "text-accent" : "text-surface-500",
                        )}
                      />
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, i) => (
              <tr
                key={i}
                className="border-b border-surface-700 hover:bg-surface-700/50 transition-colors animate-row-reveal"
                style={{ animationDelay: `${Math.min(i, 30) * 20}ms` }}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={cn(
                      "px-4 py-3",
                      col.align === "right" && "text-right",
                      col.hideOnMobile && "hidden sm:table-cell",
                    )}
                  >
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {sorted.length === 0 && (
        <div className="text-center py-8 text-surface-400 text-sm">No results found</div>
      )}
    </div>
  );
}
