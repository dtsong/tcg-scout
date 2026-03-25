"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { X, Crosshair, Layers, ShoppingCart, TrendingUp, Trophy } from "lucide-react";

const STORAGE_KEY = "scout-welcome-dismissed";

const GUIDE_ITEMS = [
  {
    icon: Layers,
    label: "Meta Tier List",
    color: "text-tier-s",
    text: "See which decks are dominating. Tiers are based on meta share: S (15%+), A (8%+), B (3%+), C (1%+), and Rogue (under 1%). Weighted shares factor in placement finish, so winning decks rank higher.",
  },
  {
    icon: Crosshair,
    label: "Archetypes",
    color: "text-tier-a",
    text: "Dive into any deck to see its core cards, inclusion rates, and tournament results. Great for tuning your list or scouting opponents.",
  },
  {
    icon: ShoppingCart,
    label: "Buy List",
    color: "text-tier-b",
    text: "Preparing for a tournament? The buy list ranks cards by priority across top-tier decks so you know what to pick up first.",
  },
  {
    icon: TrendingUp,
    label: "Trends",
    color: "text-signal-up",
    text: "Track which cards are gaining or losing play. The winning edge shows cards that appear more in 1st-place decks than the general field.",
  },
  {
    icon: Trophy,
    label: "Champions League",
    color: "text-tier-rogue",
    text: "Full decklists from Japan's largest events with translated card names.",
  },
];

export function WelcomeGuide() {
  const { format } = useParams<{ format: string }>();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Only show if not previously dismissed
    const dismissed = localStorage.getItem(STORAGE_KEY);
    if (!dismissed) setVisible(true);
  }, []);

  function dismiss() {
    setVisible(false);
    localStorage.setItem(STORAGE_KEY, "1");
  }

  if (!visible) return null;

  return (
    <section className="relative rounded-md bg-surface-800 border border-accent/20 p-5 sm:p-6">
      <button
        onClick={dismiss}
        className="absolute top-3 right-3 p-1 rounded-md text-surface-400 hover:text-slate-200 hover:bg-surface-700 transition-colors"
        aria-label="Dismiss guide"
      >
        <X className="w-4 h-4" />
      </button>

      <div className="mb-4">
        <h2 className="font-display text-base font-semibold text-slate-100">
          Welcome to Scout
        </h2>
        <p className="text-sm text-surface-300 mt-1">
          Real-time meta intelligence from Japan's City League tournaments. Here's how to use it.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {GUIDE_ITEMS.map((item) => (
          <div
            key={item.label}
            className="flex gap-3 p-3 rounded-md bg-surface-700/40"
          >
            <item.icon className={`w-4 h-4 mt-0.5 shrink-0 ${item.color}`} />
            <div>
              <span className="text-sm font-medium text-slate-200">{item.label}</span>
              <p className="text-xs text-surface-300 mt-0.5 leading-relaxed">{item.text}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 flex items-center justify-between">
        <p className="text-xs text-surface-400">
          For a full walkthrough, see the{" "}
          <Link href={`/${format}/guide`} className="text-accent hover:text-accent/80 transition-colors">
            Guide
          </Link>
          . Use the date filter above to narrow results to the last 7 or 30 days.
        </p>
        <button
          onClick={dismiss}
          className="text-xs text-accent hover:text-accent/80 transition-colors font-medium shrink-0 ml-4"
        >
          Got it
        </button>
      </div>
    </section>
  );
}
