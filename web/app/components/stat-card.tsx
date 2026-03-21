import { cn } from "@/app/lib/utils";

export function StatCard({
  label,
  value,
  unit,
  className,
  tooltip,
}: {
  label: string;
  value: string | number;
  unit?: string;
  className?: string;
  tooltip?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <span className="text-sm text-surface-300 font-body flex items-center gap-1">
        {label}
        {tooltip && (
          <span className="relative group">
            <span className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full border border-surface-500 text-surface-400 text-[9px] leading-none cursor-help">
              i
            </span>
            <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 px-2.5 py-1.5 rounded-md bg-surface-700 border border-surface-500 text-xs text-slate-300 leading-relaxed w-52 text-center opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-opacity shadow-lg z-20 pointer-events-none">
              {tooltip}
            </span>
          </span>
        )}
      </span>
      <span className="font-mono text-2xl font-medium text-slate-100 tabular-nums">
        {value}
        {unit && (
          <span className="text-sm text-surface-300 ml-1">{unit}</span>
        )}
      </span>
    </div>
  );
}
