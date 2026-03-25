import type { Metadata } from "next";
import { StartContent } from "@/app/components/start-content";

export const metadata: Metadata = {
  title: "Get Started with Scout | Pokemon TCG Meta Explorer",
  description:
    "Everything in one place. Tier lists, consensus decklists, card trends, matchup data, and tournament results from Japan's Pokemon TCG meta.",
  openGraph: {
    title: "Scout -- Everything in one place",
    description:
      "Tier lists, consensus decklists, trends, matchups, and tournament results. The fastest way to read Japan's Pokemon TCG meta.",
    type: "website",
    url: "https://scout.trainerlab.io/start",
    images: [{ url: "/images/og-start.png", width: 1200, height: 630 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Scout -- Everything in one place",
    description:
      "Tier lists, consensus decklists, trends, matchups, and tournament results. The fastest way to read Japan's Pokemon TCG meta.",
    images: ["/images/og-start.png"],
  },
};

export default function StartPage() {
  return <StartContent />;
}
