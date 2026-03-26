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
    <div className="flex items-center gap-1 overflow-x-auto border-b border-surface-600">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={cn(
            "px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px whitespace-nowrap",
            activeTab === tab.id
              ? "border-accent text-accent"
              : "border-transparent text-surface-300 hover:text-slate-200",
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
