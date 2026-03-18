import { getBuylist, getStaples, getFlex, formatHasData } from "@/app/lib/data";
import { BuylistClient } from "./buylist-client";
import Link from "next/link";

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
  return <BuylistClient buylist={buylist} staples={staples} flex={flex} />;
}
