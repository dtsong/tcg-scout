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
  CuratedPlayer,
  FormatInfo,
  PlayerDetail,
  PlayerSummary,
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

function assertSafeSegment(segment: string, label: string): string {
  if (!segment.length || segment.includes("/") || segment.includes("\\") || segment === "." || segment === "..") {
    throw new Error(`Invalid ${label}: ${segment}`);
  }
  return segment;
}

function readJsonFile<T>(...segments: string[]): T {
  const resolved = path.join(DATA_DIR, ...segments);
  const raw = fs.readFileSync(resolved, "utf-8");
  try {
    return JSON.parse(raw);
  } catch (err) {
    throw new Error(`Failed to parse JSON at ${resolved}: ${(err as Error).message}`);
  }
}

function readRootJson<T>(filename: string): T {
  return readJsonFile<T>(assertSafeSegment(filename, "filename"));
}

function splitSafePath(relativePath: string, label: string): string[] {
  return relativePath
    .split("/")
    .filter(Boolean)
    .map((segment) => assertSafeSegment(segment, label));
}

function readFormatJson<T>(format: string, filename: string): T {
  return readJsonFile<T>(
    assertSafeSegment(format, "format"),
    ...splitSafePath(filename, "filename"),
  );
}

function readScopedJson<T>(format: string, scope: string, filename: string): T {
  return readJsonFile<T>(
    assertSafeSegment(format, "format"),
    assertSafeSegment(scope, "scope"),
    assertSafeSegment(filename, "filename"),
  );
}

function readEntityJson<T>(
  format: string,
  scope: string,
  slug: string,
): T {
  return readJsonFile<T>(
    assertSafeSegment(format, "format"),
    assertSafeSegment(scope, "scope"),
    `${assertSafeSegment(slug, "slug")}.json`,
  );
}

export function getFormats(): FormatInfo[] {
  return readRootJson("formats.json");
}

/** Return the slug of the first active format, falling back to the first format with data. */
export function getDefaultFormat(): string {
  const formats = getFormats();
  const active = formats.find((f) => f.status === "active");
  if (active) return active.slug;
  const frozen = formats.find((f) => f.status === "frozen");
  const slug = frozen?.slug ?? formats[0]?.slug;
  if (!slug) {
    throw new Error(
      "[data] getDefaultFormat: formats.json contains no formats. " +
      "Run the export pipeline to generate format data."
    );
  }
  return slug;
}

/** Resolve a format slug to its display name. Throws if slug not found. Falls back to humanized slug if name_en is empty. */
export function getFormatName(format: string): string {
  const formats = getFormats();
  const match = formats.find((f) => f.slug === format);
  if (!match) {
    throw new Error(
      `getFormatName: format "${format}" not found in formats.json. Available: [${formats.map((f) => f.slug).join(", ")}]`,
    );
  }
  if (!match.name_en) {
    console.warn(`[data] getFormatName: name_en is empty for format "${format}", falling back to humanized slug`);
    // Avoid circular: inline the same logic as humanizeSlug
    return format.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }
  return match.name_en;
}

export function getMeta(format: string): MetaData {
  return readFormatJson(format, "meta.json");
}

export function getBuylist(format: string): BuylistCard[] {
  return readFormatJson(format, "buylist.json");
}

export function getStaples(format: string): StapleCard[] {
  return readFormatJson(format, "staples.json");
}

export function getFlex(format: string): StapleCard[] {
  return readFormatJson(format, "flex.json");
}

export function getTrends(format: string): TrendsData {
  // Handle both old format (cards) and new format (surging/declining)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const raw: any = readFormatJson(format, "trends.json");
  if (raw.cards && !raw.surging) {
    return { ...raw, surging: raw.cards, declining: [] };
  }
  return raw;
}

export function getWinningEdge(format: string): WinningEdgeCard[] {
  return readFormatJson(format, "winning-edge.json");
}

export function getAceSpecs(format: string): AceSpec[] {
  return readFormatJson(format, "ace-specs.json");
}

export function getArchetype(format: string, slug: string): ArchetypeDetail {
  return readEntityJson(format, "archetypes", slug);
}

/** Load archetype data, returning null for missing files (ENOENT). */
export function tryGetArchetype(format: string, slug: string): ArchetypeDetail | null {
  try {
    return getArchetype(format, slug);
  } catch (err) {
    if (isFileNotFound(err)) return null;
    throw err;
  }
}

export function getArchetypeSlugs(format: string): string[] {
  const dir = path.join(DATA_DIR, format, "archetypes");
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter((f) => f.endsWith(".json"))
    .map((f) => f.replace(".json", ""));
}

export function getCLDivision(format: string, division: string): CLDivision {
  return readEntityJson(format, "champions-league", division);
}

function isFileNotFound(err: unknown): boolean {
  return (err as NodeJS.ErrnoException).code === "ENOENT";
}

function makeSafeLoader<T>(filename: string, label: string): (format: string) => T | null {
  return (format: string): T | null => {
    try {
      return readFormatJson<T>(format, filename);
    } catch (err) {
      if (isFileNotFound(err)) return null;
      console.error(`Failed to load ${label} for ${format}:`, err);
      return null;
    }
  };
}

function makeSafeArrayLoader<T>(filename: string, label: string): (format: string) => T[] {
  return (format: string): T[] => {
    try {
      return readFormatJson<T[]>(format, filename);
    } catch (err) {
      if (isFileNotFound(err)) return [];
      console.error(`Failed to load ${label} for ${format}:`, err);
      return [];
    }
  };
}

export const getTimeline = makeSafeLoader<TimelineData>("timeline.json", "timeline");

export const getCardIndex = makeSafeArrayLoader<CardSummary>("cards/index.json", "card index");

export function getCardDetail(format: string, slug: string): CardDetail {
  return readEntityJson(format, "cards", slug);
}

export const getSynergyPairs = makeSafeArrayLoader<SynergyPair>("cards/synergy.json", "synergy pairs");

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
    const raw = readFormatJson<MetaEvolutionData | MetaEvolutionMovement[]>(
      format,
      "meta-evolution.json",
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

export const getMatchupMatrix = makeSafeLoader<MatchupMatrixData>("matchup.json", "matchup matrix");

export const getArchetypeOverlap = makeSafeLoader<OverlapMatrixData>("archetype-overlap.json", "archetype overlap");

export const getCardAnalysis = makeSafeLoader<CardAnalysisData>("card-analysis.json", "card analysis");

export const getTechForecast = makeSafeLoader<TechForecast>("tech-forecast.json", "tech forecast");

export function formatHasData(format: string): boolean {
  const metaPath = path.join(DATA_DIR, format, "meta.json");
  return fs.existsSync(metaPath);
}

export const getMetaReport = makeSafeLoader<MetaReport>("report.json", "meta report");

export const getOptimal60Index = makeSafeLoader<Optimal60Index>("optimal-60/index.json", "optimal 60 index");

export function getOptimal60(format: string, slug: string): Optimal60Detail | null {
  try {
    return readEntityJson(format, "optimal-60", slug);
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
    return readEntityJson(format, "archetype-reports", slug);
  } catch (err) {
    if (isFileNotFound(err)) return null;
    throw err;
  }
}

export function getCityLeagueIndex(format: string): CityLeagueIndex | null {
  try {
    return readFormatJson(format, "city-league-index.json");
  } catch (err) {
    if (isFileNotFound(err)) return null;
    throw err;
  }
}

export function getPlayerIndex(format: string): PlayerSummary[] | null {
  try {
    return readScopedJson(format, "players", "index.json");
  } catch (err) {
    if (isFileNotFound(err)) return null;
    throw err;
  }
}

export function getCuratedPlayers(format: string): CuratedPlayer[] | null {
  try {
    return readScopedJson(format, "players", "curated.json");
  } catch (err) {
    if (isFileNotFound(err)) return null;
    throw err;
  }
}

export function getPlayerDetail(format: string, slug: string): PlayerDetail | null {
  try {
    return readEntityJson(format, "players", slug);
  } catch (err) {
    if (isFileNotFound(err)) return null;
    throw err;
  }
}

export function getPlayerSlugs(format: string): string[] {
  const curated = getCuratedPlayers(format);
  if (!curated) return [];
  return curated.map((p) => p.slug);
}
