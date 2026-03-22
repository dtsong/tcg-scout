import { getCityLeagueIndex, getMeta, formatHasData } from "@/app/lib/data";
import { TournamentsClient } from "./tournaments-client";
import Link from "next/link";

export default async function TournamentsPage({
  params,
}: {
  params: Promise<{ format: string }>;
}) {
  const { format } = await params;

  if (!formatHasData(format)) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">No data available yet for this format.</p>
        <Link href="/" className="mt-4 inline-block text-sm text-accent">
          Back to formats
        </Link>
      </div>
    );
  }

  const meta = getMeta(format);
  const index = getCityLeagueIndex(format);

  if (!index || index.tournament_count === 0) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">No tournament data available yet.</p>
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
    <TournamentsClient
      format={format}
      index={index}
      dateRange={meta.date_range}
    />
  );
}
