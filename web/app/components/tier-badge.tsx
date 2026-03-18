import { cn } from "@/app/lib/utils";
import type { Tier } from "@/app/lib/types";

const tierConfig: Record<Tier, { bg: string; border: string; text: string }> = {
  S: { bg: "bg-tier-s/10", border: "border-l-tier-s", text: "text-tier-s" },
  A: { bg: "bg-tier-a/10", border: "border-l-tier-a", text: "text-tier-a" },
  B: { bg: "bg-tier-b/10", border: "border-l-tier-b", text: "text-tier-b" },
  C: { bg: "bg-tier-c/10", border: "border-l-tier-c", text: "text-tier-c" },
  Rogue: { bg: "bg-tier-rogue/10", border: "border-l-tier-rogue", text: "text-tier-rogue" },
};

export function TierBadge({ tier, className }: { tier: Tier; className?: string }) {
  const config = tierConfig[tier];
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 text-xs font-semibold font-[family-name:var(--font-display)] border-l-2 rounded-r-sm",
        config.bg,
        config.border,
        config.text,
        className,
      )}
    >
      {tier}
    </span>
  );
}
