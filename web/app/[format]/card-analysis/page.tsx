import { getCardAnalysis, formatHasData } from "@/app/lib/data";
import { CardAnalysisClient } from "./card-analysis-client";
import Link from "next/link";

export default async function CardAnalysisPage({
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

  const data = getCardAnalysis(format);

  if (!data || data.cards.length === 0) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">No card analysis data available yet.</p>
        <Link href={`/${format}`} className="mt-4 inline-block text-sm text-accent">Back to dashboard</Link>
      </div>
    );
  }

  return <CardAnalysisClient data={data} format={format} />;
}
