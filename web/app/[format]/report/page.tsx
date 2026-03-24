import { getMetaReport, getFormats, getFormatName } from "@/app/lib/data";
import { ReportClient } from "./report-client";
import type { Metadata } from "next";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ format: string }>;
}): Promise<Metadata> {
  const { format } = await params;
  const formatName = getFormatName(format);
  const title = `Meta Report -- ${formatName} | Scout`;
  const description = `Auto-generated meta report for the ${formatName} Pokemon TCG format. Tier analysis, top decks, and meta trends.`;
  return {
    title,
    description,
    openGraph: { title, description },
    twitter: { card: "summary", title, description },
  };
}

export async function generateStaticParams() {
  const formats = getFormats();
  return formats.map((f) => ({ format: f.slug }));
}

export default async function ReportPage({
  params,
}: {
  params: Promise<{ format: string }>;
}) {
  const { format } = await params;
  const report = getMetaReport(format);

  if (!report) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <h1 className="font-display text-2xl font-bold text-slate-100 mb-3">
          No Report Available Yet
        </h1>
        <p className="text-surface-300 max-w-md">
          The meta report for this format has not been generated yet. Check back after more tournament data is available.
        </p>
      </div>
    );
  }

  return <ReportClient report={report} format={format} />;
}
