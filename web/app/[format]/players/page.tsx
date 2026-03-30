import {
  getPlayerIndex,
  getCuratedPlayers,
  formatHasData,
} from "@/app/lib/data";
import { formatPageMetadata } from "@/app/lib/metadata";
import Link from "next/link";

export function generateMetadata({
  params,
}: {
  params: Promise<{ format: string }>;
}) {
  return formatPageMetadata(params, (formatName) => ({
    title: `Players -- ${formatName} | Scout`,
    description: `Top performing players in ${formatName} Pokemon TCG. Performance tracking, deck timelines, and notable competitors.`,
  }));
}

export default async function PlayersPage({
  params,
}: {
  params: Promise<{ format: string }>;
}) {
  const { format } = await params;

  if (!formatHasData(format)) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">
          No data available yet for this format.
        </p>
        <Link href="/" className="mt-4 inline-block text-sm text-accent">
          Back to formats
        </Link>
      </div>
    );
  }

  const curated = getCuratedPlayers(format);
  const performers = getPlayerIndex(format);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Players</h1>
        <p className="mt-1 text-sm text-surface-300">
          Notable competitors and top City League performers
        </p>
      </div>

      {curated && curated.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-white mb-4">
            Notable Players
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {curated.map((player) => (
              <Link
                key={player.player_id}
                href={`/${format}/players/${player.slug}`}
                className="block rounded-lg border border-surface-600 bg-surface-800/60 p-4 hover:border-accent/50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-semibold text-white">
                      {player.display_name}
                    </p>
                    <p className="text-xs text-surface-400">{player.country}</p>
                  </div>
                  {player.twitter_handle && (
                    <span className="text-xs text-surface-400">
                      @{player.twitter_handle}
                    </span>
                  )}
                </div>
                <div className="mt-3 flex items-center gap-4 text-sm text-surface-300">
                  <span>
                    {player.tournament_count}{" "}
                    {player.tournament_count === 1 ? "event" : "events"}
                  </span>
                  <span>Score: {player.weighted_score.toFixed(1)}</span>
                </div>
                {player.aliases.length > 0 && (
                  <p className="mt-2 text-xs text-surface-500">
                    Also known as: {player.aliases.join(", ")}
                  </p>
                )}
              </Link>
            ))}
          </div>
        </section>
      )}

      {performers && performers.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-white mb-4">
            Top City League Performers
          </h2>
          <p className="text-xs text-surface-400 mb-3">
            Players with 2+ top-cut appearances, ranked by weighted placement
            score. Common names (e.g. single-character nicknames) may represent
            multiple players.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-600 text-surface-400 text-left">
                  <th className="py-2 pr-3 font-medium">#</th>
                  <th className="py-2 pr-3 font-medium">Player</th>
                  <th className="py-2 pr-3 font-medium text-right">Events</th>
                  <th className="py-2 pr-3 font-medium text-right">Best</th>
                  <th className="py-2 pr-3 font-medium text-right">Score</th>
                  <th className="py-2 font-medium">Archetypes</th>
                </tr>
              </thead>
              <tbody>
                {performers.map((p, i) => (
                  <tr
                    key={p.slug}
                    className="border-b border-surface-700/50 hover:bg-surface-700/30"
                  >
                    <td className="py-2 pr-3 text-surface-500">{i + 1}</td>
                    <td className="py-2 pr-3 font-medium text-white">
                      {p.player_name}
                    </td>
                    <td className="py-2 pr-3 text-right text-surface-300">
                      {p.tournament_count}
                    </td>
                    <td className="py-2 pr-3 text-right text-surface-300">
                      {p.best_placement}
                    </td>
                    <td className="py-2 pr-3 text-right text-accent">
                      {p.weighted_score.toFixed(1)}
                    </td>
                    <td className="py-2 text-surface-300 text-xs">
                      {p.archetypes.slice(0, 3).join(", ")}
                      {p.archetypes.length > 3 &&
                        ` +${p.archetypes.length - 3}`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {!curated?.length && !performers?.length && (
        <div className="text-center py-24">
          <p className="text-surface-300">
            No player data available yet. Run the export pipeline to generate
            player data.
          </p>
        </div>
      )}
    </div>
  );
}
