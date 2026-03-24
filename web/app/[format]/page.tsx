import Link from "next/link";
import { getMeta, getFormats, getAceSpecs, getTrends, getWinningEdge, getTimeline, getMetaEvolution, getCardAnalysis, formatHasData } from "@/app/lib/data";
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
  const formats = getFormats();
  const formatStatus = formats.find((f) => f.slug === format)?.status;
  const aceSpecs = getAceSpecs(format);
  const trends = getTrends(format);
  const winningEdge = getWinningEdge(format);
  const timeline = getTimeline(format);
  const metaEvolution = getMetaEvolution(format);
  const cardAnalysis = getCardAnalysis(format);

  // Cross-meta staples: cards with positive impact in 3+ S/A/B-tier archetypes
  const crossMetaStaples = (cardAnalysis?.cards ?? [])
    .map((card) => {
      const tieredArchetypes = card.archetypes.filter(
        (a) => ["S", "A", "B"].includes(a.tier) && a.delta_vs_field > 0
      );
      return { card_name: card.card_name, impact: card.weighted_impact, archetype_count: tieredArchetypes.length };
    })
    .filter((c) => c.archetype_count >= 3)
    .sort((a, b) => b.archetype_count - a.archetype_count || b.impact - a.impact)
    .slice(0, 5);

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
