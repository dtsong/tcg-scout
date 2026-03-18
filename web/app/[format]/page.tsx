import Link from "next/link";
import { getMeta, getAceSpecs, getTrends, getWinningEdge, getTimeline, formatHasData } from "@/app/lib/data";
import { DashboardClient } from "./dashboard-client";

export default async function Dashboard({
  params,
}: {
  params: Promise<{ format: string }>;
}) {
  const { format } = await params;

  if (!formatHasData(format)) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <h1 className="font-display text-2xl font-bold text-slate-100 mb-3">
          No Data Yet
        </h1>
        <p className="text-surface-300 max-w-md">
          This format doesn&apos;t have any tournament data yet. Results will appear here once City League events begin.
        </p>
        <Link href="/" className="mt-6 text-sm text-accent hover:text-accent/80">
          Back to format selector
        </Link>
      </div>
    );
  }

  const meta = getMeta(format);
  const aceSpecs = getAceSpecs(format);
  const trends = getTrends(format);
  const winningEdge = getWinningEdge(format);
  const timeline = getTimeline(format);

  return (
    <DashboardClient
      format={format}
      meta={meta}
      trends={trends}
      winningEdge={winningEdge}
      aceSpecs={aceSpecs}
      timeline={timeline}
    />
  );
}
