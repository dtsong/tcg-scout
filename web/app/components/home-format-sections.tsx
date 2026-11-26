import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { FormatInfo } from "@/app/lib/types";

export function formatFreshness(generatedAt?: string): string | null {
  if (!generatedAt) return null;
  const ms = Date.now() - new Date(generatedAt).getTime();
  const hours = Math.floor(ms / 3_600_000);
  if (hours < 1) return "Updated just now";
  if (hours < 24) return `Updated ${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `Updated ${days}d ago`;
}

function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

function countLabel(n: number | undefined, noun: string): string {
  const value = n ?? 0;
  return `${value.toLocaleString()} ${noun}${value === 1 ? "" : "s"}`;
}

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <span className="font-mono text-lg font-medium text-slate-200 tabular-nums">
        {value.toLocaleString()}
      </span>
      <p className="text-xs text-surface-400 mt-0.5">{label}</p>
    </div>
  );
}

function ActiveFormatCard({ format }: { format: FormatInfo }) {
  const freshness = formatFreshness(format.generated_at);
  return (
    <Link
      href={`/${format.slug}`}
      className="group relative block bg-surface-800 border border-accent/40 rounded-xl p-6 transition-colors hover:border-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
    >
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-medium px-2 py-0.5 rounded-full border bg-accent/15 text-accent border-accent/30">
          Active
        </span>
        <ChevronRight className="w-4 h-4 text-surface-500 group-hover:text-accent transition-colors" />
      </div>
      <h3 className="font-display text-2xl font-bold text-accent">{format.name}</h3>
      <p className="text-sm text-surface-300 mt-0.5">{format.name_en}</p>
      <p className="text-xs text-surface-400 mt-3 leading-relaxed">{format.description}</p>
      <div className="mt-5 pt-4 border-t border-surface-700">
        {format.tournament_count ? (
          <div className="flex gap-6">
            <Stat value={format.tournament_count} label="Tournaments" />
            <Stat value={format.deck_count ?? 0} label="Decks" />
          </div>
        ) : (
          <p className="text-xs text-surface-400">No results yet. The first events are being collected.</p>
        )}
        <p className="text-xs text-surface-400 mt-2">
          Legal {formatDate(format.dataset_start)} to {formatDate(format.dataset_end)}
          {freshness ? `. ${freshness}` : ""}
        </p>
      </div>
    </Link>
  );
}

function UpcomingFormatCard({ format }: { format: FormatInfo }) {
  return (
    <div className="relative bg-surface-800 border border-dashed border-surface-600 rounded-xl p-6 opacity-70">
      <div className="mb-4">
        <span className="text-xs font-medium px-2 py-0.5 rounded-full border bg-surface-700 text-surface-300 border-surface-600">
          Coming soon
        </span>
      </div>
      <h3 className="font-display text-2xl font-bold text-slate-300">{format.name}</h3>
      <p className="text-sm text-surface-300 mt-0.5">{format.name_en}</p>
      <p className="text-xs text-surface-400 mt-3 leading-relaxed">{format.description}</p>
      <div className="mt-5 pt-4 border-t border-surface-700">
        <p className="text-xs text-surface-400">
          First results expected after {formatDate(format.dataset_start)}
        </p>
      </div>
    </div>
  );
}

function ArchivedFormatRow({ format }: { format: FormatInfo }) {
  return (
    <li className="border-b border-surface-700 last:border-0">
      <Link
        href={`/${format.slug}`}
        className="group grid grid-cols-[minmax(0,1fr)_1rem] md:grid-cols-[minmax(0,1fr)_11rem_7rem_6rem_1rem] items-center gap-x-6 gap-y-1 px-4 py-3 hover:bg-surface-700/40 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent"
      >
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-200 truncate group-hover:text-accent transition-colors">
            {format.name}
          </p>
          <p className="text-xs text-surface-400 truncate">{format.name_en}</p>
        </div>
        {/* Below md: dates and counts stack under the name. md+: each is its own aligned column.
            md, not sm: the fixed columns need about 500px, which leaves no room for the name at 640px. */}
        <div className="col-start-1 flex flex-wrap gap-x-4 gap-y-0.5 md:contents">
          <p className="text-xs text-surface-400 tabular-nums">
            {formatDate(format.dataset_start)} to {formatDate(format.dataset_end)}
          </p>
          <p className="text-xs text-surface-300 font-mono tabular-nums md:text-right">
            {countLabel(format.tournament_count, "tournament")}
          </p>
          <p className="text-xs text-surface-300 font-mono tabular-nums md:text-right">
            {countLabel(format.deck_count, "deck")}
          </p>
        </div>
        <ChevronRight className="w-4 h-4 text-surface-500 group-hover:text-surface-300 col-start-2 row-start-1 row-span-2 md:col-start-auto md:row-start-auto md:row-span-1" />
      </Link>
    </li>
  );
}

/**
 * Home page format list: active and upcoming formats as cards, then frozen
 * formats as a compact archive. Expects formats already ordered by
 * sortFormats().
 */
export function HomeFormatSections({ formats }: { formats: FormatInfo[] }) {
  const current = formats.filter((f) => f.status !== "frozen");
  const archived = formats.filter((f) => f.status === "frozen");

  return (
    <div className="space-y-10">
      <section aria-labelledby="active-formats-heading">
        <h2 id="active-formats-heading" className="font-display text-lg font-semibold text-slate-100 mb-4">
          Active formats
        </h2>
        {current.length === 0 ? (
          <p className="text-sm text-surface-400">No active formats right now.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {current.map((f) =>
              f.status === "active" ? (
                <ActiveFormatCard key={f.slug} format={f} />
              ) : (
                <UpcomingFormatCard key={f.slug} format={f} />
              ),
            )}
          </div>
        )}
      </section>

      {archived.length > 0 && (
        <section aria-labelledby="archived-formats-heading">
          <h2 id="archived-formats-heading" className="font-display text-lg font-semibold text-slate-100">
            Archived formats
          </h2>
          <p className="text-sm text-surface-400 mt-1 mb-4">
            Complete results for formats that have ended.
          </p>
          <ul className="bg-surface-800 border border-surface-600 rounded-xl overflow-hidden">
            {archived.map((f) => (
              <ArchivedFormatRow key={f.slug} format={f} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
