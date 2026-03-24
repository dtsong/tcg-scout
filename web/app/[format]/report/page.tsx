import { getMetaReport, getFormats } from "@/app/lib/data";
import { formatPageMetadata } from "@/app/lib/metadata";
import { ReportClient } from "./report-client";

export function generateMetadata({ params }: { params: Promise<{ format: string }> }) {
  return formatPageMetadata(params, (formatName) => ({
    title: `Meta Report -- ${formatName} | Scout`,
    description: `Auto-generated meta report for ${formatName} Pokemon TCG. Archetype analysis, meta trends, and competitive insights.`,
  }));
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
