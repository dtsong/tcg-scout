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
  pageSizes?: number[];
  defaultPageSize?: number;
}

export function DataTable<T>({
  data,
  columns,
  searchKey,
  searchPlaceholder = "Search...",
  pageSizes,
  defaultPageSize,
}: DataTableProps<T>) {
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(defaultPageSize ?? 0);

  const paginated = !!pageSizes && pageSizes.length > 0;

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

  const paged = useMemo(() => {
    if (!paginated || pageSize <= 0) return sorted;
    const start = page * pageSize;
    return sorted.slice(start, start + pageSize);
  }, [sorted, page, pageSize, paginated]);

  const totalPages = paginated && pageSize > 0 ? Math.ceil(sorted.length / pageSize) : 1;

  // Reset page when filters change
  useMemo(() => {
    setPage(0);
  }, [search, data]);

  function toggleSort(key: string) {
    if (sortCol === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(key);
      setSortDir("desc");
    }
    setPage(0);
  }

  return (
    <div>
      <div className="flex items-center justify-between gap-4 mb-4">
        {searchKey && (
          <div className="relative">
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
        {paginated && (
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-xs text-surface-400">Show</span>
            {pageSizes.map((size) => (
              <button
                key={size}
                onClick={() => { setPageSize(size); setPage(0); }}
                className={cn(
                  "px-2 py-0.5 rounded text-xs transition-colors",
                  pageSize === size
                    ? "bg-surface-600 text-slate-200"
                    : "text-surface-400 hover:text-slate-300",
                )}
              >
                {size}
              </button>
            ))}
            <button
              onClick={() => { setPageSize(0); setPage(0); }}
              className={cn(
                "px-2 py-0.5 rounded text-xs transition-colors",
                pageSize === 0
                  ? "bg-surface-600 text-slate-200"
                  : "text-surface-400 hover:text-slate-300",
              )}
            >
              All
            </button>
          </div>
        )}
      </div>
      <div className="relative">
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
            {paged.map((row, i) => (
              <tr
                key={i}
                className={`border-b border-surface-700 hover:bg-surface-700/50 transition-colors duration-[var(--duration-fast)] ${i < 20 ? "animate-stagger" : ""}`}
                style={i < 20 ? { "--index": i } as React.CSSProperties : undefined}
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
        {/* Gradient fade hint for mobile horizontal scroll */}
        <div className="absolute top-0 right-0 bottom-0 w-8 bg-gradient-to-l from-surface-800 to-transparent pointer-events-none sm:hidden" />
      </div>
      {paged.length === 0 && (
        <div className="text-center py-8 text-surface-400 text-sm">No results found</div>
      )}
      {paginated && pageSize > 0 && totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-surface-700">
          <span className="text-xs text-surface-400">
            {page * pageSize + 1}--{Math.min((page + 1) * pageSize, sorted.length)} of {sorted.length}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-2 py-1 text-xs rounded transition-colors disabled:text-surface-600 text-surface-400 hover:text-slate-300"
            >
              Prev
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="px-2 py-1 text-xs rounded transition-colors disabled:text-surface-600 text-surface-400 hover:text-slate-300"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
