import type { Metadata } from "next";
import type { ArchetypeDetail, ArchetypeSummary, MetaData } from "./types";
import { safePercent, safeInt, humanizeSlug } from "./metadata";

export const SITE_URL = "https://scout.trainerlab.io";

/**
 * Build the full public URL for an archetype sprite image.
 * Sprites are stored at /images/sprites/{filename} and served statically by Vercel.
 */
function spriteUrl(filename: string): string {
  return `${SITE_URL}/images/sprites/${filename}`;
}

/**
 * Build Open Graph + Twitter Card metadata for an archetype detail page.
 */
export function archetypeOgMetadata(
  format: string,
  formatName: string,
  arch: ArchetypeDetail,
  slug: string,
): Metadata {
  const name = arch.archetype || humanizeSlug(slug);
  const share = safePercent(arch.meta_share);
  const tier = arch.tier || "Unknown";
  const deckCount = safeInt(arch.deck_count);
  const pageUrl = `${SITE_URL}/${format}/archetypes/${slug}`;

  const title = `${name} -- ${share}% Meta Share, Tier ${tier} | Scout`;
  const description = `${name} in ${formatName}: ${share}% meta share, Tier ${tier}, ${deckCount} decks. Core cards, results, and performance analysis.`;

  // Use the first sprite as the OG image, falling back to no image
  const sprites = arch.sprite_filenames ?? [];
  const imageUrl = sprites.length > 0 ? spriteUrl(sprites[0]) : undefined;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: pageUrl,
      siteName: "Scout",
      type: "article",
      ...(imageUrl ? { images: [{ url: imageUrl, width: 68, height: 68, alt: name }] } : {}),
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      ...(imageUrl ? { images: [imageUrl] } : {}),
    },
  };
}

/**
 * Build Open Graph + Twitter Card metadata for the meta dashboard page.
 */
export function dashboardOgMetadata(
  format: string,
  formatName: string,
  meta: MetaData | null,
): Metadata {
  const title = `Meta Dashboard -- ${formatName} | Scout`;
  const pageUrl = `${SITE_URL}/${format}`;

  // Summarize top archetypes for the description
  const topArchetypes = meta?.archetypes?.slice(0, 5) ?? [];
  const topNames = topArchetypes.map((a: ArchetypeSummary) => a.archetype).join(", ");
  const deckCount = meta?.deck_count ?? 0;
  const tournamentCount = meta?.tournament_count ?? 0;

  const description = topNames
    ? `${formatName} meta tier list: ${topNames}. ${tournamentCount} tournaments, ${deckCount} decks analyzed.`
    : `Latest meta tier list for ${formatName} Pokemon TCG. Archetype rankings, trending cards, and tournament results from Japan's City Leagues.`;

  // Use the top archetype's first sprite as the OG image
  const topSprites = topArchetypes[0]?.sprite_filenames ?? [];
  const imageUrl = topSprites.length > 0 ? spriteUrl(topSprites[0]) : undefined;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: pageUrl,
      siteName: "Scout",
      type: "website",
      ...(imageUrl ? { images: [{ url: imageUrl, width: 68, height: 68, alt: formatName }] } : {}),
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      ...(imageUrl ? { images: [imageUrl] } : {}),
    },
  };
}
