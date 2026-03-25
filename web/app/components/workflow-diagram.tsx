import Link from "next/link";
import {
  Layers,
  Crosshair,
  BookOpen,
  Zap,
  TrendingUp,
  Swords,
} from "lucide-react";

const STEPS = [
  {
    number: 1,
    title: "Check the tier list",
    description: "See which decks dominate the meta",
    path: "",
    icon: Layers,
  },
  {
    number: 2,
    title: "Pick an archetype",
    description: "Explore core cards, matchups, and variants",
    path: "/archetypes",
    icon: Crosshair,
  },
  {
    number: 3,
    title: "Study the Optimal 60",
    description: "Get the consensus decklist",
    path: "/optimal-60",
    icon: BookOpen,
  },
  {
    number: 4,
    title: "Find winning cards",
    description: "Spot cards overrepresented in top finishes",
    path: "/card-analysis",
    icon: Zap,
  },
  {
    number: 5,
    title: "Track what's changing",
    description: "Monitor surging and declining cards",
    path: "/trends",
    icon: TrendingUp,
  },
  {
    number: 6,
    title: "Scout your matchups",
    description: "Check head-to-head advantages",
    path: "/archetypes",
    icon: Swords,
  },
];

export function WorkflowDiagram({
  format,
  compact = false,
}: {
  format: string;
  compact?: boolean;
}) {
  return (
    <div className="relative">
      {/* Desktop: horizontal flow */}
      <div className="hidden lg:block">
        <div className="grid grid-cols-6 gap-0 relative">
          {/* Connector line spanning all steps */}
          <div className="absolute top-6 left-[calc(100%/12)] right-[calc(100%/12)] h-px bg-gradient-to-r from-accent/60 via-accent/30 to-accent/60" />

          {STEPS.map((step) => {
            const content = (
              <div
                key={step.number}
                className={`relative flex flex-col items-center text-center ${
                  compact ? "" : "group"
                }`}
              >
                {/* Numbered circle */}
                <div
                  className={`relative z-10 w-12 h-12 rounded-full border-2 border-accent/60 bg-surface-800 flex items-center justify-center ${
                    compact
                      ? ""
                      : "group-hover:border-accent group-hover:shadow-[0_0_16px_-4px_rgba(245,158,11,0.3)] transition-all duration-200"
                  }`}
                >
                  <span className="font-mono text-sm font-bold text-accent">
                    {step.number}
                  </span>
                </div>

                {/* Title + description */}
                <div className="mt-3 px-1">
                  <p
                    className={`font-display text-xs font-semibold text-slate-200 leading-tight ${
                      compact
                        ? ""
                        : "group-hover:text-accent transition-colors duration-200"
                    }`}
                  >
                    {step.title}
                  </p>
                  <p className="text-[10px] text-surface-300 mt-1 leading-relaxed">
                    {step.description}
                  </p>
                </div>
              </div>
            );

            if (compact) {
              return (
                <div key={step.number} className="flex flex-col items-center">
                  {content}
                </div>
              );
            }

            return (
              <Link
                key={step.number}
                href={`/${format}${step.path}`}
                className="flex flex-col items-center"
              >
                {content}
              </Link>
            );
          })}
        </div>
      </div>

      {/* Mobile / Tablet: vertical flow */}
      <div className="lg:hidden space-y-0">
        {STEPS.map((step, i) => {
          const isLast = i === STEPS.length - 1;
          const StepIcon = step.icon;

          const content = (
            <div
              key={step.number}
              className={`relative flex items-start gap-4 ${
                compact ? "" : "group"
              }`}
            >
              {/* Left column: circle + connector */}
              <div className="flex flex-col items-center shrink-0">
                <div
                  className={`relative z-10 w-10 h-10 rounded-full border-2 border-accent/60 bg-surface-800 flex items-center justify-center ${
                    compact
                      ? ""
                      : "group-hover:border-accent group-hover:shadow-[0_0_16px_-4px_rgba(245,158,11,0.3)] transition-all duration-200"
                  }`}
                >
                  <span className="font-mono text-sm font-bold text-accent">
                    {step.number}
                  </span>
                </div>
                {/* Vertical connector */}
                {!isLast && (
                  <div className="w-px h-6 bg-gradient-to-b from-accent/40 to-accent/10 mt-0.5" />
                )}
              </div>

              {/* Right column: text */}
              <div className={`pt-1.5 ${isLast ? "pb-0" : "pb-4"}`}>
                <div className="flex items-center gap-2">
                  <StepIcon className="w-3.5 h-3.5 text-accent/60" />
                  <p
                    className={`font-display text-sm font-semibold text-slate-200 ${
                      compact
                        ? ""
                        : "group-hover:text-accent transition-colors duration-200"
                    }`}
                  >
                    {step.title}
                  </p>
                </div>
                <p className="text-xs text-surface-300 mt-0.5 leading-relaxed">
                  {step.description}
                </p>
              </div>
            </div>
          );

          if (compact) {
            return <div key={step.number}>{content}</div>;
          }

          return (
            <Link key={step.number} href={`/${format}${step.path}`}>
              {content}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
