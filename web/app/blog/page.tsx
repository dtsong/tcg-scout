import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Scout v1.1.0 - Format Edge, Tournament Links, and More",
  description:
    "Scout evolves from dashboard to analytics platform. New in v1.1.0: Format Edge analysis, tournament links, tooltips, and a roadmap for auto meta reports.",
  openGraph: {
    title: "Scout v1.1.0 - Format Edge, Tournament Links, and More",
    description:
      "Scout evolves from dashboard to analytics platform. New in v1.1.0: Format Edge analysis, tournament links, tooltips, and a roadmap for auto meta reports.",
    type: "article",
    url: "https://scout.trainerlab.io/blog",
  },
  twitter: {
    card: "summary_large_image",
    title: "Scout v1.1.0 - Format Edge, Tournament Links, and More",
    description:
      "Scout evolves from dashboard to analytics platform. New in v1.1.0: Format Edge analysis, tournament links, tooltips, and a roadmap for auto meta reports.",
  },
};

export default function BlogPage() {
  return (
    <article className="prose-custom">
      {/* Header */}
      <header className="mb-12">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-xs font-mono px-2 py-1 rounded bg-surface-700 border border-surface-600 text-accent">
            v1.1.0
          </span>
          <time
            dateTime="2026-03-19"
            className="text-sm text-surface-400 font-mono"
          >
            March 19, 2026
          </time>
        </div>
        <h1 className="text-3xl sm:text-4xl font-display font-bold text-slate-100 leading-tight mb-4">
          Format Edge, Tournament Links, and More
        </h1>
        <p className="text-lg text-surface-300 font-body leading-relaxed">
          Scout started as a personal tool to answer one question: what should I
          play this weekend? Here is how it became a platform.
        </p>
      </header>

      <hr className="border-surface-600 mb-12" />

      {/* The journey */}
      <section className="mb-12">
        <h2 className="text-xl font-display font-semibold text-slate-100 mb-4">
          Where it started
        </h2>
        <p className="text-surface-300 font-body leading-relaxed mb-4">
          v1.0.0 shipped with the core intelligence layer: 269 archetype detail
          pages, matchup matrices, synergy analysis, card intelligence, Champions
          League decklists, and a priority-scored buy list. The goal was to put
          the JP meta in one place, with enough depth to actually inform deck
          selection.
        </p>
        <p className="text-surface-300 font-body leading-relaxed">
          That foundation held up. But as the data grew, it became clear that
          the raw numbers needed better framing -- not just what is popular, but
          what actually performs.
        </p>
      </section>

      {/* v1.1.0 highlights */}
      <section className="mb-12">
        <h2 className="text-xl font-display font-semibold text-slate-100 mb-6">
          What is new in v1.1.0
        </h2>

        <div className="space-y-8">
          {/* Format Edge */}
          <div className="border-l-2 border-accent pl-5">
            <h3 className="text-base font-display font-semibold text-slate-100 mb-2">
              Format Edge
            </h3>
            <p className="text-surface-300 font-body leading-relaxed">
              The Card Analysis tab has been renamed and reframed as Format Edge.
              The name change is intentional: the tool is not about cataloguing
              cards, it is about identifying which cards overperform in top-4
              finishes relative to their overall play rate. A card with high
              top-4 share but low overall share is a signal -- it is ending up
              in winning lists more than average. That is the edge. A new delta
              column in card detail pages surfaces this comparison directly.
            </p>
          </div>

          {/* Tournament links */}
          <div className="border-l-2 border-surface-500 pl-5">
            <h3 className="text-base font-display font-semibold text-slate-100 mb-2">
              Tournament links
            </h3>
            <p className="text-surface-300 font-body leading-relaxed">
              Tournament names in archetype result tables now link directly to
              their Limitless pages. If you want to drill into a specific event
              -- see the full standings, cross-reference decklists -- you can
              get there in one click instead of hunting for it manually.
            </p>
          </div>

          {/* Tooltips */}
          <div className="border-l-2 border-surface-500 pl-5">
            <h3 className="text-base font-display font-semibold text-slate-100 mb-2">
              Tooltips across matrices and dashboard
            </h3>
            <p className="text-surface-300 font-body leading-relaxed">
              The matchup and heat matrices now surface contextual tooltips on
              hover. Dashboard stat cards also carry tooltip explanations for
              less obvious metrics. The data was always there; this makes it
              legible without needing to read documentation.
            </p>
          </div>

          {/* UX polish */}
          <div className="border-l-2 border-surface-500 pl-5">
            <h3 className="text-base font-display font-semibold text-slate-100 mb-2">
              Pagination and UX polish
            </h3>
            <p className="text-surface-300 font-body leading-relaxed">
              Several tables received pagination improvements to handle the full
              archetype set without performance degradation. Card names in top-4
              stats now link to their detail pages. General UX cleanup across
              the board -- tightened spacing, cleaner state transitions, reduced
              visual noise.
            </p>
          </div>
        </div>
      </section>

      {/* What's next */}
      <section className="mb-12 bg-surface-800 border border-surface-600 rounded-lg p-6">
        <h2 className="text-xl font-display font-semibold text-slate-100 mb-4">
          What is coming next
        </h2>
        <p className="text-surface-300 font-body leading-relaxed mb-4">
          Three things are on the near-term roadmap:
        </p>
        <ul className="space-y-3">
          <li className="flex gap-3">
            <span className="text-accent font-mono text-sm mt-0.5 shrink-0">01</span>
            <div>
              <span className="text-slate-200 font-body font-medium">
                Auto-generated weekly meta reports
              </span>
              <p className="text-surface-400 text-sm font-body mt-0.5">
                Structured summaries of tier shifts, card movement, and notable
                results -- published automatically after each week of tournament
                data.
              </p>
            </div>
          </li>
          <li className="flex gap-3">
            <span className="text-accent font-mono text-sm mt-0.5 shrink-0">02</span>
            <div>
              <span className="text-slate-200 font-body font-medium">
                API layer
              </span>
              <p className="text-surface-400 text-sm font-body mt-0.5">
                A lightweight read API over the meta data, so the underlying
                intelligence can power other tools and integrations.
              </p>
            </div>
          </li>
          <li className="flex gap-3">
            <span className="text-accent font-mono text-sm mt-0.5 shrink-0">03</span>
            <div>
              <span className="text-slate-200 font-body font-medium">
                Tournament prep tools
              </span>
              <p className="text-surface-400 text-sm font-body mt-0.5">
                Targeted features for players preparing for a specific event --
                expected field breakdown, matchup priority lists, card inclusion
                recommendations.
              </p>
            </div>
          </li>
        </ul>
      </section>

      {/* CTA */}
      <section className="mb-4">
        <h2 className="text-xl font-display font-semibold text-slate-100 mb-4">
          Stay in the loop
        </h2>
        <p className="text-surface-300 font-body leading-relaxed mb-6">
          Scout is updated as JP tournament data comes in. Bookmark{" "}
          <Link
            href="/"
            className="text-accent hover:text-accent/80 transition-colors"
          >
            scout.trainerlab.io
          </Link>{" "}
          and follow{" "}
          <a
            href="https://x.com/trainerlab_io"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent hover:text-accent/80 transition-colors"
          >
            @trainerlab_io
          </a>{" "}
          on X for updates when new features ship.
        </p>
      </section>
    </article>
  );
}
