"use client";

import { cn } from "@/app/lib/utils";

export interface TabItem {
  id: string;
  label: string;
}

export function Tabs({
  tabs,
  activeTab,
  onTabChange,
}: {
  tabs: readonly TabItem[];
  activeTab: string;
  onTabChange: (id: string) => void;
}) {
  if (tabs.length === 0) return null;

  function handleKeyDown(e: React.KeyboardEvent, index: number) {
    let nextIndex: number | null = null;
    if (e.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
    if (e.key === "ArrowLeft") nextIndex = (index - 1 + tabs.length) % tabs.length;
    if (nextIndex !== null) {
      e.preventDefault();
      const nextTab = document.getElementById(`tab-${tabs[nextIndex].id}`);
      if (process.env.NODE_ENV !== "production" && !nextTab) {
        console.warn(`[Tabs] Could not find element #tab-${tabs[nextIndex].id}`);
      }
      nextTab?.focus();
      onTabChange(tabs[nextIndex].id);
    }
  }

  return (
    <div
      role="tablist"
      className="inline-flex items-center gap-1 overflow-x-auto bg-surface-700/50 rounded-lg p-1 border border-surface-600"
    >
      {tabs.map((tab, index) => (
        <button
          key={tab.id}
          id={`tab-${tab.id}`}
          role="tab"
          aria-selected={activeTab === tab.id}
          aria-controls={`tabpanel-${tab.id}`}
          tabIndex={activeTab === tab.id ? 0 : -1}
          onClick={() => onTabChange(tab.id)}
          onKeyDown={(e) => handleKeyDown(e, index)}
          className={cn(
            "px-4 py-2 text-sm font-medium rounded-md transition-colors whitespace-nowrap",
            activeTab === tab.id
              ? "bg-surface-600 text-slate-100 shadow-sm"
              : "text-surface-300 hover:text-slate-200 hover:bg-surface-600/40",
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
