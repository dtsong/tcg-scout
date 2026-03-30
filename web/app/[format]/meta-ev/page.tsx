import {
  getMeta,
  getMatchupMatrix,
  formatHasData,
} from "@/app/lib/data";
import { formatPageMetadata } from "@/app/lib/metadata";
import Link from "next/link";
import { MetaEvClient } from "./meta-ev-client";

export function generateMetadata({
  params,
}: {
  params: Promise<{ format: string }>;
}) {
  return formatPageMetadata(params, (formatName) => ({
    title: `Meta EV Calculator -- ${formatName} | Scout`,
    description: `Calculate your expected win rate against the ${formatName} meta. Select a deck and see matchup-weighted performance.`,
  }));
}

export default async function MetaEvPage({
  params,
}: {
  params: Promise<{ format: string }>;
}) {
  const { format } = await params;

  if (!formatHasData(format)) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">
          No data available yet for this format.
        </p>
        <Link href="/" className="mt-4 inline-block text-sm text-accent">
          Back to formats
        </Link>
      </div>
    );
  }

  const meta = getMeta(format);
  const matchups = getMatchupMatrix(format);

  if (!matchups) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">
          Matchup data not available yet. The Meta EV calculator requires
          head-to-head win rate data.
        </p>
        <Link
          href={`/${format}`}
          className="mt-4 inline-block text-sm text-accent"
        >
          Back to dashboard
        </Link>
      </div>
    );
  }

  return (
    <MetaEvClient
      format={format}
      archetypes={meta.archetypes}
      matchups={matchups}
    />
  );
}
