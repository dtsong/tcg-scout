import { getSynergyPairs, formatHasData } from "@/app/lib/data";
import { SynergyClient } from "./synergy-client";
import Link from "next/link";

export default async function SynergyPage({
  params,
}: {
  params: Promise<{ format: string }>;
}) {
  const { format } = await params;

  if (!formatHasData(format)) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">No synergy data available yet for this format.</p>
        <Link href="/" className="mt-4 inline-block text-sm text-accent">Back to formats</Link>
      </div>
    );
  }

  const pairs = getSynergyPairs(format);

  if (pairs.length === 0) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">No synergy data available yet for this format.</p>
        <Link href={`/${format}/cards`} className="mt-4 inline-block text-sm text-accent">Back to cards</Link>
      </div>
    );
  }

  return <SynergyClient pairs={pairs} format={format} />;
}
