import { getCardDetail, getCardSlugs, getFormats } from "@/app/lib/data";
import { CardDetailClient } from "./card-detail-client";
import { notFound } from "next/navigation";

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
  } catch {
    notFound();
  }

  return <CardDetailClient card={card} format={format} />;
}
