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
  FormatInfo,
} from "./types";

const DATA_DIR = path.join(process.cwd(), "public", "data");

function readJson<T>(filePath: string): T {
  const raw = fs.readFileSync(path.join(DATA_DIR, filePath), "utf-8");
  return JSON.parse(raw);
}

export function getFormats(): FormatInfo[] {
  return readJson("formats.json");
}

export function getMeta(format: string): MetaData {
  return readJson(`${format}/meta.json`);
}

export function getBuylist(format: string): BuylistCard[] {
  return readJson(`${format}/buylist.json`);
}

export function getStaples(format: string): StapleCard[] {
  return readJson(`${format}/staples.json`);
}

export function getFlex(format: string): StapleCard[] {
  return readJson(`${format}/flex.json`);
}

export function getTrends(format: string): TrendsData {
  // Handle both old format (cards) and new format (surging/declining)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const raw: any = readJson(`${format}/trends.json`);
  if (raw.cards && !raw.surging) {
    return { ...raw, surging: raw.cards, declining: [] };
  }
  return raw;
}

export function getWinningEdge(format: string): WinningEdgeCard[] {
  return readJson(`${format}/winning-edge.json`);
}

export function getAceSpecs(format: string): AceSpec[] {
  return readJson(`${format}/ace-specs.json`);
}

export function getArchetype(format: string, slug: string): ArchetypeDetail {
  return readJson(`${format}/archetypes/${slug}.json`);
}

export function getArchetypeSlugs(format: string): string[] {
  const dir = path.join(DATA_DIR, format, "archetypes");
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter((f) => f.endsWith(".json"))
    .map((f) => f.replace(".json", ""));
}

export function getCLDivision(format: string, division: string): CLDivision {
  return readJson(`${format}/champions-league/${division}.json`);
}

export function formatHasData(format: string): boolean {
  const metaPath = path.join(DATA_DIR, format, "meta.json");
  return fs.existsSync(metaPath);
}
