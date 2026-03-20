"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";

const SCENARIOS = [
  {
    title: "Pick a deck for this weekend",
    description:
      "Check the tier list to see what's performing, then use the buy list to find what cards you need.",
    tools: "Dashboard + Buy List",
    anchor: "#dashboard",
  },
  {
    title: "Find cards that actually win",
    description:
      "See which cards appear in top-4 finishes more than their overall play rate predicts, broken down by archetype.",
    tools: "Format Edge",
    anchor: "#format-edge",
  },
  {
    title: "Track what's changing",
    description:
      "Identify surging and declining cards, spot format shifts early, and see which cards are gaining or losing play.",
    tools: "Trends + Dashboard",
    anchor: "#trends",
  },
  {
    title: "Scout a matchup",
    description:
      "Check head-to-head performance advantages and card overlap between two archetypes.",
    tools: "Archetypes + Matchup Matrix",
    anchor: "#archetypes",
  },
  {
    title: "Study winning decklists",
    description:
      "Browse full translated decklists from Japan's premier events across all divisions.",
    tools: "Champions League",
    anchor: "#champions-league",
  },
];

const TOOL_SECTIONS = [
  {
    id: "dashboard",
    title: "Dashboard",
    content:
      "Tiers are based on meta share: S (15%+), A (8-15%), B (3-8%), C (1-3%), and Rogue (under 1%). Weighted share factors in placement finish using placement weights (1st = 3.0x, 2nd = 2.5x, 3rd-4th = 2.0x, 5th-8th = 1.5x, 9th-16th = 1.2x, 17th+ = 1.0x), so decks that consistently finish well rank higher. \"Biggest Copy-Count Shifts\" highlights cards whose usage changed the most between the first and second halves of the measured period. \"Winning Edge\" compares card usage in 1st-place decks versus the overall field for S, A, and B tier archetypes. The ACE SPEC chart shows which ACE SPECs appear most across top-tier decks.",
  },
  {
    id: "archetypes",
    title: "Archetypes",
    content:
      "Browse all archetypes and their tournament results. The Performance Advantage Matrix shows head-to-head standing differentials (how much better one archetype performs when it faces another, requiring at least 10 co-occurrences). The Card Overlap Matrix uses Jaccard similarity to measure how much two archetypes share cards; 30%+ overlap suggests shared engines. Each archetype detail page shows inclusion rates, card breakdown, and tournament history.",
  },
  {
    id: "format-edge",
    title: "Format Edge",
    content:
      "Cards here are overrepresented in top-4 finishing decks compared to all decks in the field, broken down by archetype. For example, a card at 80% in top-4 decks but only 55% overall has a +25 point edge. Avg Edge averages across all archetypes where the card appears; Best Edge shows the single strongest archetype edge. This is distinct from Winning Edge (dashboard), which compares 1st-place finishes only.",
  },
  {
    id: "cards",
    title: "Cards",
    content:
      "Browse all cards tracked across archetypes. Each card shows usage rate, deck count, and average copies. Card detail pages break down usage by archetype and show which decks include the card.",
  },
  {
    id: "buy-list",
    title: "Buy List",
    content:
      "Cards are priority-scored across S, A, and B tier archetypes. Staples appear in most decks of an archetype; Flex cards appear in some builds. Higher priority means the card is widely needed across multiple top-tier decks.",
  },
  {
    id: "trends",
    title: "Trends",
    content:
      "Cards are measured for usage change between the first and second halves of the measured period. Surging cards are gaining play; declining cards are losing play. The \"Winning Edge\" table shows cards that appear more frequently in 1st-place decks compared to the overall field.",
  },
  {
    id: "champions-league",
    title: "Champions League",
    content:
      "Full translated decklists from Japan's Champions League events. Results are organized by division (Masters, Seniors, Juniors). These results are not included in archetype scoring since CL placements lack archetype classification.",
  },
  {
    id: "report",
    title: "Report",
    content:
      "Auto-generated weekly meta summaries when available. Reports cover tier movements, emerging trends, and notable meta shifts.",
  },
];

const GLOSSARY = [
  {
    id: "meta-share",
    metric: "Meta share",
    definition: "Percentage of total decks that play this archetype.",
    foundOn: "Dashboard, Archetypes",
  },
  {
    id: "weighted-share",
    metric: "Weighted share",
    definition:
      "Meta share adjusted by placement finish. Higher placements count more (1st = 3.0x, 2nd = 2.5x, etc.).",
    foundOn: "Dashboard",
  },
  {
    id: "winning-edge",
    metric: "Winning edge",
    definition:
      "Difference in card usage between 1st-place decks and the overall field.",
    foundOn: "Dashboard, Trends",
  },
  {
    id: "top-4-edge",
    metric: "Top-4 edge",
    definition:
      "Difference in card usage between top-4 finishing decks and the overall field. Avg Edge averages across archetypes; Best Edge shows the strongest single archetype.",
    foundOn: "Format Edge",
  },
  {
    id: "archetype-trend",
    metric: "Archetype trend delta",
    definition:
      "Change in meta share between the first and second halves of the measured period.",
    foundOn: "Dashboard",
  },
  {
    id: "card-trend",
    metric: "Card trend (Surging/Declining)",
    definition:
      "Change in card usage rate between the first and second halves of the measured period.",
    foundOn: "Trends, Dashboard",
  },
  {
    id: "performance-advantage",
    metric: "Performance advantage",
    definition:
      "Head-to-head standing differential when two archetypes appear in the same tournament. Minimum 10 co-occurrences.",
    foundOn: "Archetypes",
  },
  {
    id: "card-overlap",
    metric: "Card overlap",
    definition:
      "Jaccard similarity between two archetypes' card pools. 30%+ suggests a shared engine.",
    foundOn: "Archetypes",
  },
];

export function GuideClient() {
  const [openSections, setOpenSections] = useState<Set<string>>(
    new Set(["dashboard"])
  );

  function toggleSection(id: string) {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  return (
    <div className="space-y-12">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-display font-bold text-slate-100 mb-4">
          How Scout Works
        </h1>
        <p className="text-surface-300 font-body leading-relaxed max-w-3xl">
          Scout tracks Japanese Pokemon TCG tournament results and turns them
          into actionable analytics. Here is how to get the most out of it.
        </p>
      </div>

      {/* Scenario cards */}
      <section>
        <h2 className="text-xl font-display font-semibold text-slate-200 mb-4">
          What are you trying to do?
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {SCENARIOS.map((scenario) => (
            <a
              key={scenario.anchor}
              href={scenario.anchor}
              className="bg-surface-800 border border-surface-600 rounded-lg p-4 hover:border-surface-500 transition-colors block"
            >
              <p className="text-xs font-mono text-accent mb-2">
                {scenario.tools}
              </p>
              <h3 className="text-sm font-display font-semibold text-slate-200 mb-2">
                {scenario.title}
              </h3>
              <p className="text-xs text-surface-300 font-body leading-relaxed">
                {scenario.description}
              </p>
            </a>
          ))}
        </div>
      </section>

      {/* Tool sections accordion */}
      <section>
        <h2 className="text-xl font-display font-semibold text-slate-200 mb-4">
          Tools
        </h2>
        <div className="space-y-2">
          {TOOL_SECTIONS.map((section) => {
            const isOpen = openSections.has(section.id);
            return (
              <div
                key={section.id}
                id={section.id}
                className="bg-surface-800 border border-surface-600 rounded-lg overflow-hidden"
              >
                <button
                  onClick={() => toggleSection(section.id)}
                  className="w-full flex items-center justify-between p-4 text-left"
                  aria-expanded={isOpen}
                >
                  <span className="text-amber-400 font-display font-semibold">
                    {section.title}
                  </span>
                  <ChevronDown
                    className={`w-4 h-4 text-surface-400 transition-transform duration-200 ${
                      isOpen ? "rotate-180" : ""
                    }`}
                  />
                </button>
                {isOpen && (
                  <div className="px-4 pb-4 text-surface-300 text-sm font-body leading-relaxed">
                    {section.content}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* Metric Glossary */}
      <section>
        <h2 className="text-xl font-display font-semibold text-slate-200 mb-4">
          Metric Glossary
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-600">
                <th className="text-left py-2 pr-4 text-surface-400 font-display font-medium w-40">
                  Metric
                </th>
                <th className="text-left py-2 pr-4 text-surface-400 font-display font-medium">
                  Definition
                </th>
                <th className="text-left py-2 text-surface-400 font-display font-medium w-40">
                  Found on
                </th>
              </tr>
            </thead>
            <tbody>
              {GLOSSARY.map((row) => (
                <tr
                  key={row.id}
                  className="border-b border-surface-700 last:border-0"
                >
                  <td className="py-3 pr-4 text-slate-200 font-body font-medium align-top">
                    {row.metric}
                  </td>
                  <td className="py-3 pr-4 text-surface-300 font-body leading-relaxed align-top">
                    {row.definition}
                  </td>
                  <td className="py-3 text-surface-400 font-mono text-xs align-top">
                    {row.foundOn}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
