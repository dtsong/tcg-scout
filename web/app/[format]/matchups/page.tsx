import { getMatchupMatrix, formatHasData, getMeta } from "@/app/lib/data";
import { formatPageMetadata } from "@/app/lib/metadata";
import { MatchupsClient } from "./matchups-client";
import Link from "next/link";

export function generateMetadata({
  params,
}: {
  params: Promise<{ format: string }>;
}) {
  return formatPageMetadata(params, (formatName) => ({
    title: `Matchup Matrix -- ${formatName} | Scout`,
    description: `Head-to-head matchup data for top archetypes in ${formatName} Pokemon TCG. See which decks beat which.`,
  }));
}

export default async function MatchupsPage({
  params,
}: {
  params: Promise<{ format: string }>;
}) {
  const { format } = await params;

  if (!formatHasData(format)) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">
          No matchup data available yet for this format.
        </p>
        <Link href="/" className="mt-4 inline-block text-sm text-accent">
          Back to formats
        </Link>
      </div>
    );
  }

  const matchupData = getMatchupMatrix(format);
  const meta = getMeta(format);

  return (
    <MatchupsClient
      data={matchupData}
      format={format}
      tournamentCount={meta.tournament_count}
    />
  );
}
