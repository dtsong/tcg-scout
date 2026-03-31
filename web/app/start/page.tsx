import type { Metadata } from "next";
import { StartContent } from "@/app/components/start-content";
import { getDefaultFormat } from "@/app/lib/data";
import { SITE_URL } from "@/app/lib/og";

export const metadata: Metadata = {
  title: "Get Started with Scout | Pokemon TCG Meta Explorer",
  description:
    "Everything in one place. Tier lists, consensus decklists, card trends, matchup data, and tournament results from Japan's Pokemon TCG meta.",
  openGraph: {
    title: "Scout | Everything in one place",
    description:
      "Tier lists, consensus decklists, trends, matchups, and tournament results. The fastest way to read Japan's Pokemon TCG meta.",
    type: "website",
    url: `${SITE_URL}/start`,
  },
  twitter: {
    card: "summary_large_image",
    title: "Scout | Everything in one place",
    description:
      "Tier lists, consensus decklists, trends, matchups, and tournament results. The fastest way to read Japan's Pokemon TCG meta.",
  },
};

export default function StartPage() {
  return <StartContent format={getDefaultFormat()} />;
}
