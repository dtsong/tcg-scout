import { getMeta, formatHasData } from "@/app/lib/data";
import { ArchetypesClient } from "./archetypes-client";
import Link from "next/link";

export default async function ArchetypesPage({
  params,
}: {
  params: Promise<{ format: string }>;
}) {
  const { format } = await params;

  if (!formatHasData(format)) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">No archetype data available yet for this format.</p>
        <Link href="/" className="mt-4 inline-block text-sm text-accent">Back to formats</Link>
      </div>
    );
  }

  const meta = getMeta(format);
  return (
    <ArchetypesClient
      archetypes={meta.archetypes}
      format={format}
      dateRange={meta.date_range}
    />
  );
}
