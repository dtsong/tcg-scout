import { getCardIndex, getMeta, formatHasData } from "@/app/lib/data";
import { CardsClient } from "./cards-client";
import Link from "next/link";

export default async function CardsPage({
  params,
}: {
  params: Promise<{ format: string }>;
}) {
  const { format } = await params;

  if (!formatHasData(format)) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">No card data available yet for this format.</p>
        <Link href="/" className="mt-4 inline-block text-sm text-accent">Back to formats</Link>
      </div>
    );
  }

  const cards = getCardIndex(format);
  const meta = getMeta(format);

  if (cards.length === 0) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">No card data available yet for this format.</p>
        <Link href={`/${format}`} className="mt-4 inline-block text-sm text-accent">Back to dashboard</Link>
      </div>
    );
  }

  return (
    <CardsClient
      cards={cards}
      format={format}
      dateRange={meta.date_range}
    />
  );
}
