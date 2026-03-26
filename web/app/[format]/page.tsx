import Link from "next/link";
import type { Metadata } from "next";
import { getMeta, getFormats, getAceSpecs, getTrends, getWinningEdge, getTimeline, getMetaEvolution, getCardAnalysis, formatHasData, getFormatName } from "@/app/lib/data";
import { computeCrossMetaStaples } from "@/app/lib/utils";
import { dashboardOgMetadata } from "@/app/lib/og";
import { DashboardClient } from "./dashboard-client";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ format: string }>;
}): Promise<Metadata> {
  const { format } = await params;
  const formatName = getFormatName(format);
  let meta = null;
  try {
    meta = getMeta(format);
  } catch (err) {
    console.error(`[generateMetadata] Failed to load meta for format "${format}":`, err);
  }
  return dashboardOgMetadata(format, formatName, meta);
}

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
  const formats = getFormats();
  const formatStatus = formats.find((f) => f.slug === format)?.status;
  const aceSpecs = getAceSpecs(format);
  const trends = getTrends(format);
  const winningEdge = getWinningEdge(format);
  const timeline = getTimeline(format);
  const metaEvolution = getMetaEvolution(format);
  const cardAnalysis = getCardAnalysis(format);

  const crossMetaStaples = computeCrossMetaStaples(cardAnalysis?.cards ?? []);

  return (
    <DashboardClient
      format={format}
      formatStatus={formatStatus}
      meta={meta}
      trends={trends}
      winningEdge={winningEdge}
      aceSpecs={aceSpecs}
      timeline={timeline}
      metaEvolution={metaEvolution.highlights}
      crossMetaStaples={crossMetaStaples}
    />
  );
}
