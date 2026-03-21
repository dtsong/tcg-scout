import {
  getArchetypeReport,
  getArchetypeSlugs,
  getFormats,
} from "@/app/lib/data";
import { ReportClient } from "./report-client";

export async function generateStaticParams() {
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

export async function generateMetadata({
  params,
}: {
  params: Promise<{ format: string; slug: string }>;
}) {
  const { format, slug } = await params;
  const report = getArchetypeReport(format, slug);
  const name = report?.archetype ?? slug;
  return {
    title: `${name} Deep Dive | Scout`,
    description: `Weighted consensus decklist, tech evolution, and performance analysis for ${name}.`,
  };
}

export default async function ArchetypeReportPage({
  params,
}: {
  params: Promise<{ format: string; slug: string }>;
}) {
  const { format, slug } = await params;
  const report = getArchetypeReport(format, slug);

  if (!report) {
    return (
      <div className="text-center py-16">
        <h1 className="font-display text-xl font-semibold text-slate-100 mb-2">
          Report Not Available
        </h1>
        <p className="text-sm text-surface-400">
          Deep dive report data has not been generated for this archetype yet.
        </p>
      </div>
    );
  }

  return <ReportClient report={report} format={format} />;
}
