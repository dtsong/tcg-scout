import { Nav } from "@/app/components/nav";
import { DateFilterProvider } from "@/app/components/date-filter-provider";
import { getFormats, getMeta, formatHasData } from "@/app/lib/data";
import type { FormatInfo } from "@/app/lib/types";

export function generateStaticParams() {
  return getFormats().map((f) => ({ format: f.slug }));
}

export default async function FormatLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ format: string }>;
}) {
  const { format } = await params;

  const hasData = formatHasData(format);
  const dateRange = hasData
    ? getMeta(format).date_range
    : { start: "2026-01-01", end: "2026-12-31" };
  const formats = getFormats();

  return (
    <DateFilterProvider initialDateRange={dateRange}>
      <Nav format={format} formats={formats} />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
      <footer className="border-t border-surface-700 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-surface-400">
            <p>
              Data sourced from{" "}
              <a href="https://limitlesstcg.com" target="_blank" rel="noopener noreferrer" className="text-accent hover:text-accent/80">
                LimitlessTCG
              </a>{" "}
              (City League results) and{" "}
              <a href="https://pokemon-card.com" target="_blank" rel="noopener noreferrer" className="text-accent hover:text-accent/80">
                pokemon-card.com
              </a>{" "}
              (Champions League decklists)
            </p>
          </div>
        </div>
      </footer>
    </DateFilterProvider>
  );
}
