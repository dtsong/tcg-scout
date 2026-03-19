import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

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
