import Link from "next/link";
import { Nav } from "@/app/components/nav";
import { MetaTicker } from "@/app/components/meta-ticker";
import { FormatSidebar } from "@/app/components/format-sidebar";
import { DateFilterProvider } from "@/app/components/date-filter-provider";
import { getFormats, getMeta, formatHasData } from "@/app/lib/data";
import { daysUntil } from "@/app/lib/utils";
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
  const meta = hasData ? getMeta(format) : null;
  const dateRange = meta?.date_range ?? { start: "2026-01-01", end: "2026-12-31" };
  const formats = getFormats();
  const rotationDays = meta?.rotation_date
    ? Math.max(0, daysUntil(meta.rotation_date))
    : undefined;

  return (
    <DateFilterProvider initialDateRange={dateRange}>
      {meta && (
        <MetaTicker
          formatName={meta.format?.name_en ?? format}
          tournamentCount={meta.tournament_count}
          deckCount={meta.deck_count}
          generatedAt={meta.generated_at}
          rotationDays={rotationDays}
        />
      )}
      <Nav format={format} formats={formats} />
      <div className="max-w-7xl mx-auto flex">
        {meta && (
          <aside className="hidden lg:block w-56 shrink-0 sticky top-16 h-[calc(100vh-4rem)] overflow-y-auto border-r border-surface-700 px-4 py-6">
            <FormatSidebar meta={meta} format={format} formats={formats} rotationDays={rotationDays} />
          </aside>
        )}
        <main className="flex-1 min-w-0 px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>
      </div>
      <footer className="border-t border-surface-700 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-4">
          <nav className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-surface-400">
            <Link href={`/${format}`} className="hover:text-slate-200 transition-colors">Dashboard</Link>
            <Link href={`/${format}/optimal-60`} className="hover:text-slate-200 transition-colors">Optimal 60</Link>
            <Link href={`/${format}/archetypes`} className="hover:text-slate-200 transition-colors">Archetypes</Link>
            <Link href={`/${format}/matchups`} className="hover:text-slate-200 transition-colors">Matchups</Link>
            <Link href={`/${format}/cards`} className="hover:text-slate-200 transition-colors">Cards</Link>
            <Link href={`/${format}/card-analysis`} className="hover:text-slate-200 transition-colors">Format Edge</Link>
            <Link href={`/${format}/buylist`} className="hover:text-slate-200 transition-colors">Buy List</Link>
            <Link href={`/${format}/trends`} className="hover:text-slate-200 transition-colors">Trends</Link>
            <Link href={`/${format}/champions`} className="hover:text-slate-200 transition-colors">Champions League</Link>
            <span className="text-surface-600">|</span>
            <Link href={`/${format}/guide`} className="hover:text-slate-200 transition-colors">Guide</Link>
            <Link href="/blog" className="hover:text-slate-200 transition-colors">Blog</Link>
          </nav>
          <p className="text-xs text-surface-400">
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
      </footer>
    </DateFilterProvider>
  );
}
