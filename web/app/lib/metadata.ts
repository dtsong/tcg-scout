import type { Metadata } from "next";
import { getFormatName } from "@/app/lib/data";

/**
 * Build page metadata for a format-level page (no slug needed).
 * Handles the async params unwrapping and format name resolution that
 * every [format]/* page repeats.
 */
export async function formatPageMetadata(
  params: Promise<{ format: string }>,
  build: (formatName: string) => { title: string; description: string },
): Promise<Metadata> {
  const { format } = await params;
  const formatName = getFormatName(format);
  return build(formatName);
}

/**
 * Safely format a percentage value, returning "0.0" for NaN/Infinity.
 */
export function safePercent(value: number): string {
  if (!Number.isFinite(value)) {
    console.warn(`[metadata] safePercent received non-finite value: ${value}`);
    return "0.0";
  }
  return value.toFixed(1);
}

/**
 * Safely round to an integer, returning 0 for NaN/Infinity.
 */
export function safeInt(value: number): number {
  if (!Number.isFinite(value)) {
    console.warn(`[metadata] safeInt received non-finite value: ${value}`);
    return 0;
  }
  return Math.round(value);
}
