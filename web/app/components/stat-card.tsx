import { cn } from "@/app/lib/utils";

export function StatCard({
  label,
  value,
  unit,
  className,
}: {
  label: string;
  value: string | number;
  unit?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <span className="text-sm text-surface-300 font-body">
        {label}
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
