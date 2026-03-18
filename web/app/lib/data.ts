import fs from "fs";
import path from "path";
import type {
  MetaData,
  BuylistCard,
  StapleCard,
  TrendsData,
  WinningEdgeCard,
  AceSpec,
  ArchetypeDetail,
  CLDivision,
} from "./types";

const DATA_DIR = path.join(process.cwd(), "public", "data");

function readJson<T>(filePath: string): T {
  const raw = fs.readFileSync(path.join(DATA_DIR, filePath), "utf-8");
  return JSON.parse(raw);
}

export function getMeta(): MetaData {
  return readJson("meta.json");
}

export function getBuylist(): BuylistCard[] {
  return readJson("buylist.json");
}

export function getStaples(): StapleCard[] {
  return readJson("staples.json");
}

export function getFlex(): StapleCard[] {
  return readJson("flex.json");
}

export function getTrends(): TrendsData {
  // Handle both old format (cards) and new format (surging/declining)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const raw: any = readJson("trends.json");
  if (raw.cards && !raw.surging) {
    return { ...raw, surging: raw.cards, declining: [] };
  }
  return raw;
}

export function getWinningEdge(): WinningEdgeCard[] {
  return readJson("winning-edge.json");
}

export function getAceSpecs(): AceSpec[] {
  return readJson("ace-specs.json");
}

export function getArchetype(slug: string): ArchetypeDetail {
  return readJson(`archetypes/${slug}.json`);
}

export function getArchetypeSlugs(): string[] {
  const dir = path.join(DATA_DIR, "archetypes");
  return fs.readdirSync(dir)
    .filter((f) => f.endsWith(".json"))
    .map((f) => f.replace(".json", ""));
}

export function getCLDivision(division: string): CLDivision {
  return readJson(`champions-league/${division}.json`);
}
