import { getTechForecast, formatHasData } from "@/app/lib/data";
import { formatPageMetadata } from "@/app/lib/metadata";
import { ForecastClient } from "./forecast-client";
import Link from "next/link";

export function generateMetadata({ params }: { params: Promise<{ format: string }> }) {
  return formatPageMetadata(params, (formatName) => ({
    title: `Tech Forecast -- ${formatName} | Scout`,
    description: `Card adoption trends and tech forecasts for ${formatName} Pokemon TCG. Track rising and falling tech choices across the meta.`,
  }));
}

export default async function ForecastPage({
  params,
}: {
  params: Promise<{ format: string }>;
}) {
  const { format } = await params;

  if (!formatHasData(format)) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">No forecast data available yet for this format.</p>
        <Link href="/" className="mt-4 inline-block text-sm text-accent">Back to formats</Link>
      </div>
    );
  }

  const forecast = getTechForecast(format);

  if (!forecast || forecast.cards.length === 0) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">No tech card forecast data available yet.</p>
        <Link href={`/${format}`} className="mt-4 inline-block text-sm text-accent">Back to overview</Link>
      </div>
    );
  }

  return <ForecastClient forecast={forecast} format={format} />;
}
