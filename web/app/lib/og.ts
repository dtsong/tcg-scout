import type { Metadata } from "next";
import type { ArchetypeDetail, ArchetypeSummary, MetaData } from "./types";
import { safePercent, safeInt, humanizeSlug } from "./metadata";

export const SITE_URL = "https://scout.trainerlab.io";

const OG_DEFAULT_IMAGE = {
  url: `${SITE_URL}/og-default.png`,
  width: 1200,
  height: 630,
  alt: "Scout - JP Meta Explorer for Pokemon TCG",
};

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

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: pageUrl,
      siteName: "Scout",
      type: "article",
      images: [OG_DEFAULT_IMAGE],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [OG_DEFAULT_IMAGE.url],
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

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: pageUrl,
      siteName: "Scout",
      type: "website",
      images: [OG_DEFAULT_IMAGE],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [OG_DEFAULT_IMAGE.url],
    },
  };
}
