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
  TimelineData,
  CardSummary,
  CardDetail,
  SynergyPair,
  MetaEvolutionMovement,
  MatchupMatrixData,
  OverlapMatrixData,
  CardAnalysisData,
  TechForecast,
} from "./types";

const DATA_DIR = path.join(process.cwd(), "public", "data");

function readJson<T>(filePath: string): T {
  const resolved = path.resolve(DATA_DIR, filePath);
  if (!resolved.startsWith(DATA_DIR + path.sep) && resolved !== DATA_DIR) {
    throw new Error(`Path traversal blocked: ${filePath}`);
  }
  const raw = fs.readFileSync(resolved, "utf-8");
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

function isFileNotFound(err: unknown): boolean {
  return (err as NodeJS.ErrnoException).code === "ENOENT";
}

export function getTimeline(format: string): TimelineData | null {
  try {
    return readJson(`${format}/timeline.json`);
  } catch (err) {
    if (isFileNotFound(err)) return null;
    console.error(`Failed to load timeline for ${format}:`, err);
    return null;
  }
}

export function getCardIndex(format: string): CardSummary[] {
  try {
    return readJson(`${format}/cards/index.json`);
  } catch (err) {
    if (isFileNotFound(err)) return [];
    console.error(`Failed to load card index for ${format}:`, err);
    return [];
  }
}

export function getCardDetail(format: string, slug: string): CardDetail {
  return readJson(`${format}/cards/${slug}.json`);
}

export function getSynergyPairs(format: string): SynergyPair[] {
  try {
    return readJson(`${format}/cards/synergy.json`);
  } catch (err) {
    if (isFileNotFound(err)) return [];
    console.error(`Failed to load synergy pairs for ${format}:`, err);
    return [];
  }
}

export function getCardSlugs(format: string): string[] {
  const dir = path.join(DATA_DIR, format, "cards");
  if (!fs.existsSync(dir)) return [];
  const reserved = new Set(["index.json", "synergy.json"]);
  return fs.readdirSync(dir)
    .filter((f) => f.endsWith(".json") && !reserved.has(f))
    .map((f) => f.replace(".json", ""));
}

export function getMetaEvolution(format: string): MetaEvolutionMovement[] {
  try {
    return readJson(`${format}/meta-evolution.json`);
  } catch (err) {
    if (isFileNotFound(err)) return [];
    console.error(`Failed to load meta evolution for ${format}:`, err);
    return [];
  }
}

export function getMatchupMatrix(format: string): MatchupMatrixData | null {
  try {
    return readJson(`${format}/matchup.json`);
  } catch (err) {
    if (isFileNotFound(err)) return null;
    console.error(`Failed to load matchup matrix for ${format}:`, err);
    return null;
  }
}

export function getArchetypeOverlap(format: string): OverlapMatrixData | null {
  try {
    return readJson(`${format}/archetype-overlap.json`);
  } catch (err) {
    if (isFileNotFound(err)) return null;
    console.error(`Failed to load archetype overlap for ${format}:`, err);
    return null;
  }
}

export function getCardAnalysis(format: string): CardAnalysisData | null {
  try {
    return readJson(`${format}/card-analysis.json`);
  } catch (err) {
    if (isFileNotFound(err)) return null;
    console.error(`Failed to load card analysis for ${format}:`, err);
    return null;
  }
}

export function getTechForecast(format: string): TechForecast | null {
  try {
    return readJson(`${format}/tech-forecast.json`);
  } catch (err) {
    if (isFileNotFound(err)) return null;
    console.error(`Failed to load tech forecast for ${format}:`, err);
    return null;
  }
}

export function formatHasData(format: string): boolean {
  const metaPath = path.join(DATA_DIR, format, "meta.json");
  return fs.existsSync(metaPath);
}
