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
  ArchetypeReport,
  CLDivision,
  CityLeagueIndex,
  FormatInfo,
  TimelineData,
  CardSummary,
  CardDetail,
  SynergyPair,
  MetaEvolutionMovement,
  MetaEvolutionData,
  MatchupMatrixData,
  OverlapMatrixData,
  CardAnalysisData,
  TechForecast,
  MetaReport,
  Optimal60Index,
  Optimal60Detail,
} from "./types";

const DATA_DIR = path.join(process.cwd(), "public", "data");

function readJson<T>(filePath: string): T {
  const resolved = path.resolve(DATA_DIR, filePath);
  if (!resolved.startsWith(DATA_DIR + path.sep) && resolved !== DATA_DIR) {
    throw new Error(`Path traversal blocked: ${filePath}`);
  }
  const raw = fs.readFileSync(resolved, "utf-8");
  try {
    return JSON.parse(raw);
  } catch (err) {
    throw new Error(`Failed to parse JSON at ${resolved}: ${(err as Error).message}`);
  }
}

export function getFormats(): FormatInfo[] {
  return readJson("formats.json");
}

export function getFormatName(format: string): string {
  const formats = getFormats();
  const found = formats.find((f) => f.slug === format);
  if (!found) {
    throw new Error(
      `getFormatName: format "${format}" not found in formats.json. Available: [${formats.map((f) => f.slug).join(", ")}]`,
    );
  }
  if (!found.name_en) {
    console.warn(`[data] getFormatName: name_en is empty for format "${format}", falling back to humanized slug`);
    return format.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }
  return found.name_en;
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

export function getMetaEvolution(format: string): MetaEvolutionData {
  const empty: MetaEvolutionData = { highlights: [], movements: [] };
  try {
    const raw = readJson<MetaEvolutionData | MetaEvolutionMovement[]>(
      `${format}/meta-evolution.json`
    );
    // Support both old (bare array) and new (object) formats
    if (Array.isArray(raw)) {
      console.warn(
        `[data] meta-evolution.json for "${format}" uses legacy array format`
      );
      return { highlights: raw, movements: raw };
    }
    return raw;
  } catch (err) {
    if (isFileNotFound(err)) return empty;
    throw err;
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

export function getMetaReport(format: string): MetaReport | null {
  try {
    return readJson(`${format}/report.json`);
  } catch (err) {
    if (isFileNotFound(err)) return null;
    console.error(`Failed to load meta report for ${format}:`, err);
    return null;
  }
}

export function getOptimal60Index(format: string): Optimal60Index | null {
  try {
    return readJson(`${format}/optimal-60/index.json`);
  } catch (err) {
    if (isFileNotFound(err)) return null;
    console.error(`Failed to load optimal 60 index for ${format}:`, err);
    return null;
  }
}

export function getOptimal60(format: string, slug: string): Optimal60Detail | null {
  try {
    return readJson(`${format}/optimal-60/${slug}.json`);
  } catch (err) {
    if (isFileNotFound(err)) return null;
    console.error(`Failed to load optimal 60 for ${format}/${slug}:`, err);
    return null;
  }
}

export function getOptimal60Slugs(format: string): string[] {
  const dir = path.join(DATA_DIR, format, "optimal-60");
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter((f) => f.endsWith(".json") && f !== "index.json")
    .map((f) => f.replace(".json", ""));
}

export function getArchetypeReport(
  format: string,
  slug: string,
): ArchetypeReport | null {
  try {
    return readJson(`${format}/archetype-reports/${slug}.json`);
  } catch (err) {
    if (isFileNotFound(err)) return null;
    throw err;
  }
}

export function getCityLeagueIndex(format: string): CityLeagueIndex | null {
  try {
    return readJson(`${format}/city-league-index.json`);
  } catch (err) {
    if (isFileNotFound(err)) return null;
    throw err;
  }
}

