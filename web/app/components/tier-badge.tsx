import { cn } from "@/app/lib/utils";
import type { Tier } from "@/app/lib/types";

const tierConfig: Record<
  Tier,
  { bg: string; ring: string; text: string; label: string }
> = {
  S: {
    bg: "bg-gradient-to-br from-amber-400/20 to-amber-600/10",
    ring: "ring-amber-400/50",
    text: "text-amber-400",
    label: "S",
  },
  A: {
    bg: "bg-gradient-to-br from-teal-400/20 to-teal-600/10",
    ring: "ring-teal-400/50",
    text: "text-teal-400",
    label: "A",
  },
  B: {
    bg: "bg-gradient-to-br from-blue-400/20 to-blue-600/10",
    ring: "ring-blue-400/50",
    text: "text-blue-400",
    label: "B",
  },
  C: {
    bg: "bg-gradient-to-br from-slate-400/20 to-slate-500/10",
    ring: "ring-slate-400/40",
    text: "text-slate-400",
    label: "C",
  },
  Rogue: {
    bg: "bg-gradient-to-br from-purple-400/20 to-purple-600/10",
    ring: "ring-purple-400/40",
    text: "text-purple-400",
    label: "R",
  },
};

export function TierBadge({ tier, className }: { tier: Tier; className?: string }) {
  const config = tierConfig[tier];
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center w-7 h-7 text-xs font-bold font-display rounded-full ring-1",
        config.bg,
        config.ring,
        config.text,
        className,
      )}
    >
      {config.label}
    </span>
  );
}
