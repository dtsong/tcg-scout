import type { Metadata } from "next";
import { getFormats, getOptimal60Index, getFormatName } from "@/app/lib/data";
import { Optimal60Client } from "./optimal-60-client";

export function generateStaticParams() {
  return getFormats().map((f) => ({ format: f.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ format: string }>;
}): Promise<Metadata> {
  const { format } = await params;
  const formatName = getFormatName(format);
  const title = `Optimal 60 -- ${formatName} | Scout`;
  const description = `Data-backed optimal decklists for top ${formatName} archetypes, powered by Champions League results and the broader meta.`;
  return {
    title,
    description,
  };
}

export default async function Optimal60Page({
  params,
}: {
  params: Promise<{ format: string }>;
}) {
  const { format } = await params;
  const index = getOptimal60Index(format);

  if (!index || index.archetypes.length === 0) {
    return (
      <div className="text-center py-16">
        <h1 className="font-display text-xl font-semibold text-slate-100 mb-2">
          Optimal 60 Not Available
        </h1>
        <p className="text-sm text-surface-400">
          Champions League data has not been imported for this format yet.
        </p>
      </div>
    );
  }

  return <Optimal60Client index={index} format={format} />;
}
