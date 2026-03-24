import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { CardAnalysisEntry, CrossMetaStaple } from "@/app/lib/types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPlacement(placement: number | null): string {
  if (placement === null) return "—";
  const suffix = { 1: "st", 2: "nd", 3: "rd" }[
    placement < 20 ? placement : placement % 10
  ] ?? "th";
  return `${placement}${suffix}`;
}

export function formatPct(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function daysUntil(dateStr: string): number {
  const target = new Date(dateStr);
  const now = new Date();
  return Math.ceil((target.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
}

export function slugify(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

export function computeCrossMetaStaples(cards: CardAnalysisEntry[], limit = 5): CrossMetaStaple[] {
  return cards
    .map((card) => {
      const tieredArchetypes = card.archetypes.filter(
        (a) => ["S", "A", "B"].includes(a.tier) && a.delta_vs_field > 0
      );
      return { card_name: card.card_name, weighted_impact: card.weighted_impact, tiered_archetype_count: tieredArchetypes.length };
    })
    .filter((c) => c.tiered_archetype_count >= 3)
    .sort((a, b) => b.tiered_archetype_count - a.tiered_archetype_count || b.weighted_impact - a.weighted_impact)
    .slice(0, limit);
}
