import { cn } from "@/app/lib/utils";
import type { Urgency } from "@/app/lib/types";

const urgencyConfig: Record<Urgency, { bg: string; text: string }> = {
  URGENT: { bg: "bg-urgency-urgent/10", text: "text-urgency-urgent" },
  HIGH: { bg: "bg-urgency-high/10", text: "text-urgency-high" },
  MODERATE: { bg: "bg-urgency-moderate/10", text: "text-urgency-moderate" },
};

export function UrgencyBadge({ urgency, className }: { urgency: Urgency; className?: string }) {
  const config = urgencyConfig[urgency];
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-sm",
        config.bg,
        config.text,
        className,
      )}
    >
      {urgency}
    </span>
  );
}
