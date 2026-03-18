import { getTrends, getWinningEdge } from "@/app/lib/data";
import { TrendsClient } from "./trends-client";

export default function TrendsPage() {
  const trends = getTrends();
  const winningEdge = getWinningEdge();
  return <TrendsClient trends={trends} winningEdge={winningEdge} />;
}
