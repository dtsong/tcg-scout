"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { TierBadge } from "@/app/components/tier-badge";
import { SpriteRow } from "@/app/components/sprite-row";
import { StatCard } from "@/app/components/stat-card";
import { formatPct, formatPlacement } from "@/app/lib/utils";
import type { ArchetypeReport } from "@/app/lib/types";
import { ConsensusDeck } from "./consensus-deck";
import { TechEvolutionChart } from "./tech-evolution-chart";
import { NotableTechs } from "./notable-techs";
import { PlacementDistribution } from "./placement-distribution";

export function ReportClient({
  report,
  format,
  hasOptimal60 = false,
}: {
  report: ArchetypeReport;
  format: string;
  hasOptimal60?: boolean;
}) {
  const generatedDate = new Date(report.generated_at).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <div className="space-y-8">
      {/* Back link */}
      <Link
        href={`/${format}/archetypes/${report.slug}`}
        className="inline-flex items-center gap-1.5 text-sm text-surface-400 hover:text-slate-300 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to {report.archetype}
      </Link>

      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <TierBadge tier={report.tier} />
          <SpriteRow filenames={report.sprite_filenames ?? []} size={32} />
          <div>
            <h1 className="font-display text-2xl font-bold text-slate-100">
              {report.archetype}
            </h1>
            <p className="text-xs text-surface-400">
              Deep Dive Report &middot; {generatedDate}
            </p>
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 mt-4">
          <StatCard label="Tier" value={report.tier} />
          <StatCard label="Meta Share" value={formatPct(report.meta_share)} />
          <StatCard label="Decks" value={report.deck_count} />
          <StatCard label="Best Finish" value={formatPlacement(report.best_placement)} />
        </div>
      </div>

      {/* Abstract */}
      {report.narrative?.summary && (
        <div className="bg-surface-800 border-l-4 border-amber-500 rounded-r-lg p-5">
          <p className="text-sm text-slate-300 leading-relaxed">
            {report.narrative.summary}
          </p>
        </div>
      )}

      {/* Consensus 60 */}
      {report.consensus_60 && (
        <section>
          <h2 className="font-display text-lg font-semibold text-slate-100 mb-1">
            Consensus 60
          </h2>
          <p className="text-xs text-surface-400 mb-4">
            Weighted by finish position across {report.deck_count} decklists.
            Core = 75%+ inclusion, Common = 50%+, Tech = below 50%.
          </p>
          <ConsensusDeck
            cards={report.consensus_60.cards}
            qualityScore={report.consensus_60.quality_score}
            totalPokemon={report.consensus_60.total_pokemon}
            totalTrainer={report.consensus_60.total_trainer}
            totalEnergy={report.consensus_60.total_energy}
          />
          {report.narrative?.consensus_rationale && (
            <p className="text-sm text-slate-400 leading-relaxed mt-4">
              {report.narrative.consensus_rationale}
            </p>
          )}
        </section>
      )}

      {/* Optimal 60 callout */}
      {hasOptimal60 && (
        <Link
          href={`/${format}/optimal-60`}
          className="flex items-center gap-3 p-4 bg-teal-500/5 border border-teal-500/20 rounded-lg hover:bg-teal-500/10 transition-colors"
        >
          <span className="text-teal-400 text-sm font-medium">
            Optimal 60 Available
          </span>
          <span className="text-xs text-surface-400">
            See the CL-validated recommended list incorporating Champions League results
          </span>
        </Link>
      )}

      {/* Tech Evolution */}
      {report.tech_evolution && report.tech_evolution.cards.length > 0 && (
        <section>
          <h2 className="font-display text-lg font-semibold text-slate-100 mb-1">
            Tech Evolution
          </h2>
          <p className="text-xs text-surface-400 mb-4">
            Card adoption rates across {report.tech_evolution.weeks.length} weeks.
            Toggle cards to compare trends.
          </p>
          <TechEvolutionChart
            weeks={report.tech_evolution.weeks}
            cards={report.tech_evolution.cards}
          />
          {report.narrative?.tech_evolution_analysis && (
            <p className="text-sm text-slate-400 leading-relaxed mt-4">
              {report.narrative.tech_evolution_analysis}
            </p>
          )}
        </section>
      )}

      {/* Notable Techs */}
      {report.notable_techs.length > 0 && (
        <section>
          <h2 className="font-display text-lg font-semibold text-slate-100 mb-1">
            Notable Tech Changes
          </h2>
          <p className="text-xs text-surface-400 mb-4">
            Biggest card adoption and drop events in the timeline.
          </p>
          <div className="bg-surface-800 border border-surface-600 rounded-lg p-4">
            <NotableTechs techs={report.notable_techs} />
          </div>
        </section>
      )}

      {/* Placement Distribution */}
      {report.placement_distribution.length > 0 && (
        <section>
          <h2 className="font-display text-lg font-semibold text-slate-100 mb-1">
            Performance
          </h2>
          <p className="text-xs text-surface-400 mb-4">
            Finish distribution across {report.tournament_count} tournaments.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-6 mb-4">
            <StatCard label="Tournaments" value={report.tournament_count} />
            <StatCard
              label="Weighted Share"
              value={formatPct(report.weighted_share)}
            />
          </div>
          <div className="bg-surface-800 border border-surface-600 rounded-lg p-4">
            <PlacementDistribution brackets={report.placement_distribution} />
          </div>
        </section>
      )}

      {/* Back link */}
      <div className="pt-4 border-t border-surface-700">
        <Link
          href={`/${format}/archetypes/${report.slug}`}
          className="inline-flex items-center gap-1.5 text-sm text-surface-400 hover:text-slate-300 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to {report.archetype}
        </Link>
      </div>
    </div>
  );
}
