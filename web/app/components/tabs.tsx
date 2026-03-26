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
  tabs: TabItem[];
  activeTab: string;
  onTabChange: (id: string) => void;
}) {
  return (
    <div className="inline-flex items-center gap-1 overflow-x-auto bg-surface-700/50 rounded-lg p-1 border border-surface-600">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
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
