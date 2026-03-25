"use client";

import Link from "next/link";
import {
  Layers,
  Crosshair,
  Zap,
  TrendingUp,
  Swords,
  Trophy,
  ArrowRight,
  BookOpen,
} from "lucide-react";
import { WorkflowDiagram } from "./workflow-diagram";

const DEFAULT_FORMAT = "ninja-spinner";

const FEATURE_CARDS = [
  {
    icon: Layers,
    title: "Read the meta",
    description:
      "Tier list with meta share and weighted share. See which decks are S-tier and which are falling off.",
    path: "",
  },
  {
    icon: BookOpen,
    title: "Pick a deck",
    description:
      "Optimal 60 consensus decklists built from Champions League and City League data.",
    path: "/optimal-60",
  },
  {
    icon: Zap,
    title: "Find winning cards",
    description:
      "Format Edge shows cards overrepresented in top-4 finishes. Winning Edge tracks 1st-place signals.",
    path: "/card-analysis",
  },
  {
    icon: TrendingUp,
    title: "Track what's changing",
    description:
      "Surging and declining cards, meta shifts, and tech forecast watchlists updated weekly.",
    path: "/trends",
  },
  {
    icon: Swords,
    title: "Scout matchups",
    description:
      "Head-to-head performance matrix and card overlap analysis between archetypes.",
    path: "/archetypes",
  },
  {
    icon: Trophy,
    title: "Study decklists",
    description:
      "Full translated Champions League decklists from Masters, Seniors, and Juniors divisions.",
    path: "/champions",
  },
];

export function StartContent() {
  return (
    <div className="space-y-16">
      {/* Hero */}
      <section className="text-center">
        <h1 className="font-display text-4xl sm:text-5xl font-bold text-slate-100 tracking-tight">
          Everything in one place
        </h1>
        <p className="mt-4 text-lg text-surface-300 max-w-2xl mx-auto leading-relaxed">
          Scout consolidates tier lists, consensus decklists, card trends,
          matchup data, and tournament results from Japan&apos;s Pokemon TCG
          meta into a single platform.
        </p>

        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            href={`/${DEFAULT_FORMAT}`}
            className="inline-flex items-center gap-2 px-6 py-3 bg-accent text-surface-900 font-display font-semibold text-sm rounded-lg hover:bg-accent/90 transition-colors"
          >
            Jump into the meta
            <ArrowRight className="w-4 h-4" />
          </Link>
          <a
            href="#workflow"
            className="inline-flex items-center gap-2 px-6 py-3 border border-surface-600 text-surface-300 font-display font-medium text-sm rounded-lg hover:border-surface-500 hover:text-slate-200 transition-colors"
          >
            See the workflow
          </a>
        </div>

        {/* Nihil Zero callout */}
        <div className="mt-8 mx-auto max-w-xl">
          <Link
            href="/nihil-zero"
            className="block bg-surface-800 border border-amber-500/20 rounded-lg px-5 py-3.5 hover:border-amber-500/40 transition-colors group"
          >
            <p className="text-sm text-amber-400 font-display font-semibold">
              Post-rotation preview
            </p>
            <p className="text-xs text-surface-300 mt-1">
              Nihil Zero mirrors the upcoming international post-rotation format
              (April 10th).{" "}
              <span className="text-accent group-hover:text-accent/80 transition-colors">
                Explore the data
              </span>
            </p>
          </Link>
        </div>
      </section>

      {/* Workflow Steps */}
      <section id="workflow">
        <div className="text-center mb-8">
          <h2 className="font-display text-2xl font-bold text-slate-100">
            How to use Scout
          </h2>
          <p className="mt-2 text-sm text-surface-300">
            Follow these steps to get the most out of the platform
          </p>
        </div>

        <div className="bg-surface-800 border border-surface-600 rounded-xl p-6 sm:p-8">
          <WorkflowDiagram format={DEFAULT_FORMAT} />
        </div>

        {/* Download link placeholder: uncomment when scout-workflow.png is added to web/public/images/
        <div className="mt-4 text-center">
          <a
            href="/images/scout-workflow.png"
            download="scout-workflow.png"
            className="inline-flex items-center gap-2 text-xs text-surface-400 hover:text-surface-300 transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            Save workflow image for sharing
          </a>
        </div>
        */}
      </section>

      {/* Feature Highlights */}
      <section>
        <div className="text-center mb-8">
          <h2 className="font-display text-2xl font-bold text-slate-100">
            What you can do
          </h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURE_CARDS.map((card) => (
            <Link
              key={card.title}
              href={`/${DEFAULT_FORMAT}${card.path}`}
              className="group bg-surface-800 border border-surface-600 rounded-lg p-5 hover:border-surface-500 transition-colors"
            >
              <card.icon className="w-5 h-5 text-accent mb-3" />
              <h3 className="font-display text-sm font-semibold text-slate-200 group-hover:text-accent transition-colors">
                {card.title}
              </h3>
              <p className="text-xs text-surface-300 mt-1.5 leading-relaxed">
                {card.description}
              </p>
            </Link>
          ))}
        </div>
      </section>

      {/* Format Spotlight */}
      <section>
        <div className="text-center mb-8">
          <h2 className="font-display text-2xl font-bold text-slate-100">
            Choose a format
          </h2>
          <p className="mt-2 text-sm text-surface-300">
            Each format tracks a distinct competitive season
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <Link
            href="/ninja-spinner"
            className="group bg-surface-800 border border-surface-600 rounded-xl p-6 hover:border-teal-500/40 hover:shadow-[0_0_24px_-4px_rgba(20,184,166,0.15)] transition-all"
          >
            <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full border bg-teal-500/15 text-teal-400 border-teal-500/30">
              Active
            </span>
            <h3 className="font-display text-xl font-bold text-teal-400 mt-3">
              Ninja Spinner
            </h3>
            <p className="text-xs text-surface-300 mt-2 leading-relaxed">
              Current Japanese rotation format. Receiving new City League data
              daily.
            </p>
          </Link>

          <Link
            href="/nihil-zero"
            className="group bg-surface-800 border border-surface-600 rounded-xl p-6 hover:border-amber-500/40 hover:shadow-[0_0_24px_-4px_rgba(245,158,11,0.15)] transition-all"
          >
            <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full border bg-surface-700 text-surface-300 border-surface-500">
              Complete
            </span>
            <h3 className="font-display text-xl font-bold text-amber-400 mt-3">
              Nihil Zero
            </h3>
            <p className="text-xs text-surface-300 mt-2 leading-relaxed">
              430 tournaments archived. Mirrors the upcoming international
              post-rotation format (April 10th).
            </p>
          </Link>
        </div>
      </section>

      {/* Guide cross-reference */}
      <section className="bg-surface-800 border border-surface-600 rounded-lg p-5">
        <h3 className="font-display text-sm font-semibold text-slate-200">
          Looking for metric definitions?
        </h3>
        <p className="text-xs text-surface-300 mt-1.5 leading-relaxed">
          This page is the quickstart: where to go first and in what order.
          The{" "}
          <Link
            href={`/${DEFAULT_FORMAT}/guide`}
            className="text-accent hover:text-accent/80 transition-colors"
          >
            Guide
          </Link>{" "}
          explains each tool and metric in depth, including weighted share
          calculations, tier thresholds, and trend methodology.
        </p>
      </section>

      {/* Footer CTA */}
      <section className="text-center pb-4">
        <p className="text-lg text-surface-300 font-display">Ready to start?</p>
        <Link
          href={`/${DEFAULT_FORMAT}`}
          className="inline-flex items-center gap-2 mt-4 px-6 py-3 bg-accent text-surface-900 font-display font-semibold text-sm rounded-lg hover:bg-accent/90 transition-colors"
        >
          Open the dashboard
          <ArrowRight className="w-4 h-4" />
        </Link>
        <div className="flex items-center justify-center gap-4 mt-6">
          <a
            href="https://github.com/dtsong/tcg-scout"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs text-surface-300 hover:text-slate-200 transition-colors"
          >
            <svg
              className="w-3.5 h-3.5"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
            </svg>
            GitHub
          </a>
          <a
            href="https://x.com/pokedansong"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs text-surface-300 hover:text-slate-200 transition-colors"
          >
            <svg
              className="w-3.5 h-3.5"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
            </svg>
            @pokedansong
          </a>
        </div>
      </section>
    </div>
  );
}
