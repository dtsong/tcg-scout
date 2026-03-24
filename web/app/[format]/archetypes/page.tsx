import type { Metadata } from "next";
import { getMeta, getArchetypeOverlap, getMatchupMatrix, formatHasData, getFormatName } from "@/app/lib/data";
import { ArchetypesClient } from "./archetypes-client";
import Link from "next/link";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ format: string }>;
}): Promise<Metadata> {
  const { format } = await params;
  const formatName = getFormatName(format);
  const title = `Archetypes -- ${formatName} | Scout`;
  const description = `All archetypes in the ${formatName} Pokemon TCG meta. Tier rankings, meta share, overlap matrix, and matchup data.`;
  return {
    title,
    description,
  };
}

export default async function ArchetypesPage({
  params,
}: {
  params: Promise<{ format: string }>;
}) {
  const { format } = await params;

  if (!formatHasData(format)) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">No archetype data available yet for this format.</p>
        <Link href="/" className="mt-4 inline-block text-sm text-accent">Back to formats</Link>
      </div>
    );
  }

  const meta = getMeta(format);
  const overlap = getArchetypeOverlap(format);
  const matchup = getMatchupMatrix(format);
  return (
    <ArchetypesClient
      archetypes={meta.archetypes}
      format={format}
      dateRange={meta.date_range}
      overlapMatrix={overlap}
      matchupMatrix={matchup}
    />
  );
}
