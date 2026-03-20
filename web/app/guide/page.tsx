import type { Metadata } from "next";
import { GuideClient } from "./guide-client";

export const metadata: Metadata = {
  title: "How Scout Works | Scout",
  description:
    "Learn how to use Scout's meta analytics tools to pick decks, find winning cards, track trends, and scout matchups.",
  openGraph: {
    title: "How Scout Works | Scout",
    description:
      "Learn how to use Scout's meta analytics tools to pick decks, find winning cards, track trends, and scout matchups.",
  },
};

export default function GuidePage() {
  return <GuideClient />;
}
