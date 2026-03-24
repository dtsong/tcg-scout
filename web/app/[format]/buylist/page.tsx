import { getBuylist, getStaples, getFlex, getMeta, formatHasData } from "@/app/lib/data";
import { formatPageMetadata } from "@/app/lib/metadata";
import { BuylistClient } from "./buylist-client";
import Link from "next/link";

export function generateMetadata({ params }: { params: Promise<{ format: string }> }) {
  return formatPageMetadata(params, (formatName) => ({
    title: `Buy List -- ${formatName} | Scout`,
    description: `Priority-ranked buy list for competitive ${formatName} Pokemon TCG decks. Staples, flex picks, and where each card fits.`,
  }));
}

export default async function BuylistPage({
  params,
}: {
  params: Promise<{ format: string }>;
}) {
  const { format } = await params;

  if (!formatHasData(format)) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">No buy list data available yet for this format.</p>
        <Link href="/" className="mt-4 inline-block text-sm text-accent">Back to formats</Link>
      </div>
    );
  }

  const buylist = getBuylist(format);
  const staples = getStaples(format);
  const flex = getFlex(format);
  const meta = getMeta(format);
  return <BuylistClient buylist={buylist} staples={staples} flex={flex} dateRange={meta.date_range} />;
}
