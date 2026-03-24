import type { Metadata } from "next";
import { getCardDetail, getCardSlugs, getFormats, getFormatName, getCardAnalysis } from "@/app/lib/data";
import { safePercent } from "@/app/lib/metadata";
import { CardDetailClient } from "./card-detail-client";
import { notFound } from "next/navigation";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ format: string; slug: string }>;
}): Promise<Metadata> {
  const { format, slug } = await params;
  const card = getCardDetail(format, slug);
  const usage = safePercent(card.usage_pct);
  const formatName = getFormatName(format);
  return {
    title: `${card.card_name} -- ${usage}% Usage | Scout`,
    description: `${card.card_name} appears in ${usage}% of ${formatName} decks across ${Number.isFinite(card.unique_archetypes) ? card.unique_archetypes : 0} archetypes. Usage trends, synergy partners, and decklist data.`,
  };
}

export const dynamicParams = false;

export function generateStaticParams() {
  const formats = getFormats();
  const params: { format: string; slug: string }[] = [];
  for (const fmt of formats) {
    const slugs = getCardSlugs(fmt.slug);
    for (const slug of slugs) {
      params.push({ format: fmt.slug, slug });
    }
  }
  return params;
}

export default async function CardDetailPage({
  params,
}: {
  params: Promise<{ format: string; slug: string }>;
}) {
  const { format, slug } = await params;

  let card;
  try {
    card = getCardDetail(format, slug);
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") {
      notFound();
    }
    throw err;
  }

  const analysis = getCardAnalysis(format);
  const analysisEntry = analysis?.cards.find((c) => c.card_name === card.card_name);
  const top4Deltas = analysisEntry?.archetypes;

  return <CardDetailClient card={card} format={format} top4Deltas={top4Deltas} />;
}
