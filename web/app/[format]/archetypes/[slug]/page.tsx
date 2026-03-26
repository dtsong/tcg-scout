import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { tryGetArchetype, getArchetypeReport, getArchetypeSlugs, getFormats, getFormatName, getMatchupMatrix, getOptimal60Index } from "@/app/lib/data";
import { archetypeOgMetadata } from "@/app/lib/og";
import { ArchetypeDetailClient } from "./archetype-detail-client";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ format: string; slug: string }>;
}): Promise<Metadata> {
  const { format, slug } = await params;
  const arch = tryGetArchetype(format, slug);
  if (!arch) {
    console.warn(`[metadata] archetype file not found for ${format}/${slug}`);
    return { title: "Archetype Not Found | Scout" };
  }
  if (!arch.archetype) {
    console.warn(`[metadata] archetype name is empty for ${format}/${slug}`);
  }
  if (!arch.tier) {
    console.warn(`[metadata] tier is missing for ${format}/${slug}`);
  }
  const formatName = getFormatName(format);
  return archetypeOgMetadata(format, formatName, arch, slug);
}

export function generateStaticParams() {
  const formats = getFormats();
  const params: { format: string; slug: string }[] = [];
  for (const fmt of formats) {
    const slugs = getArchetypeSlugs(fmt.slug);
    for (const slug of slugs) {
      params.push({ format: fmt.slug, slug });
    }
  }
  return params;
}

export default async function ArchetypeDetailPage({
  params,
}: {
  params: Promise<{ format: string; slug: string }>;
}) {
  const { format, slug } = await params;
  const arch = tryGetArchetype(format, slug);
  if (!arch) notFound();

  const matchupData = getMatchupMatrix(format);
  const hasReport = getArchetypeReport(format, slug) !== null;
  const optimal60Index = getOptimal60Index(format);
  const hasOptimal60 = optimal60Index?.archetypes.some((a) => a.slug === slug) ?? false;

  return (
    <ArchetypeDetailClient
      arch={arch}
      matchupData={matchupData}
      format={format}
      slug={slug}
      hasReport={hasReport}
      hasOptimal60={hasOptimal60}
    />
  );
}
