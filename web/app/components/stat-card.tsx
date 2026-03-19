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
          <span
            title={tooltip}
            className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full border border-surface-500 text-surface-400 text-[9px] leading-none cursor-help"
          >
            i
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
