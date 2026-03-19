import { getCardDetail, getCardSlugs, getFormats } from "@/app/lib/data";
import { CardDetailClient } from "./card-detail-client";

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
  const card = getCardDetail(format, slug);

  return <CardDetailClient card={card} format={format} />;
}
