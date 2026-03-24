export function DeltaValue({ delta, size = "sm" }: { delta: number; size?: "sm" | "lg" }) {
  if (delta === 0) return <span className="font-mono text-surface-400">0.0</span>;
  const positive = delta > 0;
  const sizeClass = size === "lg" ? "text-sm" : "text-xs";
  return (
    <span className={`font-mono tabular-nums ${sizeClass} ${positive ? "text-emerald-400" : "text-red-400"}`}>
      {positive ? "+" : ""}{delta.toFixed(1)}
    </span>
  );
}
