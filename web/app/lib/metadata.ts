import type { Metadata } from "next";
import { getFormatName } from "@/app/lib/data";

const SITE_URL = "https://scout.trainerlab.io";

/**
 * Build page metadata for a format-level page (no slug needed).
 * Handles the async params unwrapping and format name resolution that
 * every [format]/* page repeats. Includes OpenGraph and Twitter Card tags.
 */
export async function formatPageMetadata(
  params: Promise<{ format: string }>,
  build: (formatName: string) => { title: string; description: string },
): Promise<Metadata> {
  const { format } = await params;
  const formatName = getFormatName(format);
  const { title, description } = build(formatName);

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      siteName: "Scout",
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
    },
  };
}

/** Capitalize a hyphenated slug for display (e.g. "nihil-zero" -> "Nihil Zero"). */
export function humanizeSlug(slug: string): string {
  return slug.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Safely format a percentage value, returning "0.0" for NaN/Infinity.
 * Logs a console.error for non-finite inputs.
 */
export function safePercent(value: number): string {
  if (!Number.isFinite(value)) {
    console.error(`[metadata] safePercent received non-finite value: ${value}`);
    return "0.0";
  }
  return value.toFixed(1);
}

/**
 * Safely round to an integer, returning 0 for NaN/Infinity.
 * Logs a console.error for non-finite inputs.
 */
export function safeInt(value: number): number {
  if (!Number.isFinite(value)) {
    console.error(`[metadata] safeInt received non-finite value: ${value}`);
    return 0;
  }
  return Math.round(value);
}
