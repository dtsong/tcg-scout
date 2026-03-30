import {
  getPlayerDetail,
  getPlayerSlugs,
  formatHasData,
} from "@/app/lib/data";
import Link from "next/link";
import type { Metadata } from "next";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ format: string; slug: string }>;
}): Promise<Metadata> {
  const { format, slug } = await params;
  const player = getPlayerDetail(format, slug);
  const name = player?.display_name ?? slug;
  return {
    title: `${name} -- Players | Scout`,
    description: `Tournament history and deck timeline for ${name}.`,
  };
}

export async function generateStaticParams({
  params: parentParams,
}: {
  params: Promise<{ format: string }>;
}) {
  const { format } = await parentParams;
  if (!formatHasData(format)) return [];
  return getPlayerSlugs(format).map((slug) => ({ slug }));
}

export default async function PlayerDetailPage({
  params,
}: {
  params: Promise<{ format: string; slug: string }>;
}) {
  const { format, slug } = await params;

  const player = getPlayerDetail(format, slug);

  if (!player) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">Player not found.</p>
        <Link
          href={`/${format}/players`}
          className="mt-4 inline-block text-sm text-accent"
        >
          Back to players
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <Link
          href={`/${format}/players`}
          className="text-sm text-surface-400 hover:text-accent"
        >
          Players
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-white">
          {player.display_name}
        </h1>
        <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-surface-300">
          <span>{player.country}</span>
          {player.twitter_handle && (
            <a
              href={`https://x.com/${player.twitter_handle}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:underline"
            >
              @{player.twitter_handle}
            </a>
          )}
          {player.blog_url && (
            <a
              href={player.blog_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:underline"
            >
              Blog
            </a>
          )}
          {player.youtube_url && (
            <a
              href={player.youtube_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:underline"
            >
              YouTube
            </a>
          )}
        </div>
        {player.notes && (
          <p className="mt-2 text-sm text-surface-400">{player.notes}</p>
        )}
        {player.aliases.length > 0 && (
          <p className="mt-1 text-xs text-surface-500">
            City League aliases: {player.aliases.join(", ")}
          </p>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <div className="rounded-lg border border-surface-600 bg-surface-800/60 p-4">
          <p className="text-xs text-surface-400">Linked Events</p>
          <p className="mt-1 text-2xl font-bold text-white">
            {player.tournament_count}
          </p>
        </div>
        <div className="rounded-lg border border-surface-600 bg-surface-800/60 p-4">
          <p className="text-xs text-surface-400">Weighted Score</p>
          <p className="mt-1 text-2xl font-bold text-accent">
            {player.weighted_score.toFixed(1)}
          </p>
        </div>
        {player.deck_timeline.length > 0 && (
          <div className="rounded-lg border border-surface-600 bg-surface-800/60 p-4">
            <p className="text-xs text-surface-400">Archetypes Played</p>
            <p className="mt-1 text-2xl font-bold text-white">
              {new Set(player.deck_timeline.map((d) => d.archetype)).size}
            </p>
          </div>
        )}
      </div>

      {/* Deck Timeline */}
      {player.deck_timeline.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-white mb-4">
            Deck Timeline
          </h2>
          <div className="space-y-2">
            {player.deck_timeline.map((entry, i) => (
              <div
                key={`${entry.date}-${i}`}
                className="flex items-center gap-4 rounded-lg border border-surface-700/50 bg-surface-800/40 px-4 py-3"
              >
                <span className="text-sm text-surface-400 w-24 shrink-0">
                  {entry.date}
                </span>
                <span className="text-sm font-medium text-white flex-1">
                  {entry.archetype}
                </span>
                <span className="text-sm text-surface-300">
                  #{entry.standing}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Full Placement History */}
      {player.placements.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-white mb-4">
            Placement History
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-600 text-surface-400 text-left">
                  <th className="py-2 pr-3 font-medium">Date</th>
                  <th className="py-2 pr-3 font-medium">Tournament</th>
                  <th className="py-2 pr-3 font-medium text-right">
                    Standing
                  </th>
                  <th className="py-2 font-medium">Archetype</th>
                </tr>
              </thead>
              <tbody>
                {player.placements.map((p, i) => (
                  <tr
                    key={i}
                    className="border-b border-surface-700/50 hover:bg-surface-700/30"
                  >
                    <td className="py-2 pr-3 text-surface-400">{p.date}</td>
                    <td className="py-2 pr-3 text-white">
                      {p.tournament_name}
                    </td>
                    <td className="py-2 pr-3 text-right text-surface-300">
                      #{p.standing}
                    </td>
                    <td className="py-2 text-surface-300">{p.archetype}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {player.placements.length === 0 && (
        <div className="text-center py-12 text-surface-400">
          <p>
            No City League placements linked yet. Use{" "}
            <code className="text-xs bg-surface-700 px-1.5 py-0.5 rounded">
              scout players link
            </code>{" "}
            to connect tournament aliases to this player.
          </p>
        </div>
      )}
    </div>
  );
}
