import { getMetaEvolution, formatHasData } from "@/app/lib/data";
import { formatPageMetadata } from "@/app/lib/metadata";
import { ShiftsClient } from "./shifts-client";
import Link from "next/link";

export function generateMetadata({ params }: { params: Promise<{ format: string }> }) {
  return formatPageMetadata(params, (formatName) => ({
    title: `Meta Shifts -- ${formatName} | Scout`,
    description: `Track how the ${formatName} Pokemon TCG meta is evolving. Card adoptions, drops, and week-over-week changes across archetypes.`,
  }));
}

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
