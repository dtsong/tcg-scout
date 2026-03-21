import { getMetaEvolution, formatHasData } from "@/app/lib/data";
import { ShiftsClient } from "./shifts-client";
import Link from "next/link";

export default async function ShiftsPage({
  params,
}: {
  params: Promise<{ format: string }>;
}) {
  const { format } = await params;

  if (!formatHasData(format)) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">No data available yet for this format.</p>
        <Link href="/" className="mt-4 inline-block text-sm text-accent">Back to formats</Link>
      </div>
    );
  }

  const metaEvolution = getMetaEvolution(format);
  return <ShiftsClient format={format} movements={metaEvolution.movements} />;
}
