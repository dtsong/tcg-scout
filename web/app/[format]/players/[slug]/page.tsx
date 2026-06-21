import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getFormats,
  getFormatName,
  getPlayerDetail,
  getPlayerSlugs,
} from "@/app/lib/data";

export function generateStaticParams() {
  const params: { format: string; slug: string }[] = [];
  for (const fmt of getFormats()) {
    for (const slug of getPlayerSlugs(fmt.slug)) {
      params.push({ format: fmt.slug, slug });
    }
  }
  return params;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ format: string; slug: string }>;
}): Promise<Metadata> {
  const { format, slug } = await params;
  const player = getPlayerDetail(format, slug);
  if (!player) return { title: "Player Not Found | Scout" };

  const formatName = getFormatName(format);
  return {
    title: `${player.display_name} -- ${formatName} | Scout`,
    description: `${player.display_name}'s Pokemon TCG tournament results, archetype history, and notable finishes in ${formatName}.`,
  };
}

export default async function PlayerDetailPage({
  params,
}: {
  params: Promise<{ format: string; slug: string }>;
}) {
  const { format, slug } = await params;
  const player = getPlayerDetail(format, slug);
  if (!player) notFound();

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link href={`/${format}/players`} className="text-sm text-accent hover:text-accent-light">
            Back to players
          </Link>
          <h1 className="mt-3 text-2xl font-bold text-white">{player.display_name}</h1>
          <p className="mt-1 text-sm text-surface-300">
            {player.country} · {player.tournament_count} tracked events · Score {player.weighted_score.toFixed(1)}
          </p>
        </div>
        {player.twitter_handle && (
          <a
            href={`https://x.com/${player.twitter_handle}`}
            className="rounded-md border border-surface-600 px-3 py-1.5 text-sm text-surface-200 hover:border-accent/50"
          >
            @{player.twitter_handle}
          </a>
        )}
      </div>

      {player.notes && (
        <section className="rounded-lg border border-surface-700 bg-surface-800/60 p-4">
          <h2 className="text-sm font-semibold text-white">Notes</h2>
          <p className="mt-2 text-sm text-surface-300">{player.notes}</p>
        </section>
      )}

      {player.aliases.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-white">Known Aliases</h2>
          <p className="mt-2 text-sm text-surface-300">{player.aliases.join(", ")}</p>
        </section>
      )}

      <section>
        <h2 className="text-lg font-semibold text-white mb-4">Deck Timeline</h2>
        <div className="overflow-x-auto rounded-lg border border-surface-700">
          <table className="w-full text-sm">
            <thead className="bg-surface-800 text-left text-surface-400">
              <tr>
                <th className="px-4 py-2 font-medium">Date</th>
                <th className="px-4 py-2 font-medium">Archetype</th>
                <th className="px-4 py-2 font-medium text-right">Finish</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-700">
              {player.deck_timeline.map((entry) => (
                <tr key={`${entry.date}-${entry.archetype}-${entry.standing}`}>
                  <td className="px-4 py-2 text-surface-300">{entry.date}</td>
                  <td className="px-4 py-2 text-white">{entry.archetype}</td>
                  <td className="px-4 py-2 text-right text-surface-300">#{entry.standing}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-white mb-4">Placements</h2>
        <div className="space-y-2">
          {player.placements.map((placement) => (
            <div
              key={`${placement.date}-${placement.tournament_name}-${placement.standing}`}
              className="rounded-lg border border-surface-700 bg-surface-800/40 p-4"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-medium text-white">{placement.tournament_name}</p>
                  <p className="mt-1 text-sm text-surface-400">
                    {placement.date} · {placement.archetype}
                  </p>
                </div>
                <span className="text-sm font-semibold text-accent">#{placement.standing}</span>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
