import { getCLDivision, formatHasData } from "@/app/lib/data";
import { ChampionsClient } from "./champions-client";
import Link from "next/link";
import fs from "fs";
import path from "path";

export default async function ChampionsPage({
  params,
}: {
  params: Promise<{ format: string }>;
}) {
  const { format } = await params;

  const clDir = path.join(process.cwd(), "public", "data", format, "champions-league");
  const hasCL = fs.existsSync(path.join(clDir, "masters.json"));

  if (!formatHasData(format) || !hasCL) {
    return (
      <div className="text-center py-24">
        <p className="text-surface-300">No Champions League data available yet for this format.</p>
        <Link href="/" className="mt-4 inline-block text-sm text-accent">Back to formats</Link>
      </div>
    );
  }

  const juniors = getCLDivision(format, "juniors");
  const seniors = getCLDivision(format, "seniors");
  const masters = getCLDivision(format, "masters");

  return (
    <ChampionsClient
      divisions={{ juniors, seniors, masters }}
    />
  );
}
