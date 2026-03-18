import { getTrends, getWinningEdge, formatHasData } from "@/app/lib/data";
import { TrendsClient } from "./trends-client";
import Link from "next/link";

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

  const trends = getTrends(format);
  const winningEdge = getWinningEdge(format);
  return <TrendsClient trends={trends} winningEdge={winningEdge} />;
}
