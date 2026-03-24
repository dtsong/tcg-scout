"use client";

import { GuideContent } from "@/app/components/guide-content";

export function GuideClient({ format = "ninja-spinner" }: { format?: string }) {
  return <GuideContent format={format} />;
}
