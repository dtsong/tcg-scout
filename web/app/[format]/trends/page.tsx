import type { Metadata } from "next";
import { getTrends, getWinningEdge, getMeta, formatHasData, getFormatName } from "@/app/lib/data";
import { TrendsClient } from "./trends-client";
import Link from "next/link";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ format: string }>;
}): Promise<Metadata> {
  const { format } = await params;
  const formatName = getFormatName(format);
  const title = `Card Trends -- ${formatName} | Scout`;
  const description = `Surging and declining cards in ${formatName} Pokemon TCG. See which cards are gaining or losing popularity across the meta.`;
  return {
    title,
    description,
  };
}

export default async function TrendsPage({
  params,
}: {
  params: Promise<{ format: string }>;
}) {
  const { format } = await params;

  if (!formatHasData(format)) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">No trend data available yet for this format.</p>
        <Link href="/" className="mt-4 inline-block text-sm text-accent">Back to formats</Link>
      </div>
    );
  }

  const meta = getMeta(format);
  const trends = getTrends(format);
  const winningEdge = getWinningEdge(format);
  return (
    <TrendsClient
      trends={trends}
      winningEdge={winningEdge}
      format={format}
      dateRange={meta.date_range}
    />
  );
}
