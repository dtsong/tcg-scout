"use client";

import { useParams } from "next/navigation";
import { GuideContent } from "@/app/components/guide-content";

export function GuideClient() {
  const { format } = useParams<{ format: string }>();
  return <GuideContent format={format} />;
}
