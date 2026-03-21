import type { Metadata } from "next";
import { getFormats } from "@/app/lib/data";
import { GuideClient } from "./guide-client";

export const metadata: Metadata = {
  title: "How Scout Works | Scout",
  description:
    "Learn how to use Scout's meta analytics tools to pick decks, find winning cards, track trends, and scout matchups.",
};

export function generateStaticParams() {
  return getFormats().map((f) => ({ format: f.slug }));
}

export default function GuidePage() {
  return <GuideClient />;
}
