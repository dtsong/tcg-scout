import type { FormatInfo } from "./types";

export type FormatRegion = NonNullable<FormatInfo["region"]>;

export interface FormatRegionGroup {
  region: FormatRegion;
  label: string;
  formats: FormatInfo[];
}

/** Display order and labels for each tournament circuit. */
const REGIONS: { region: FormatRegion; label: string }[] = [
  { region: "jp", label: "Japan City League" },
  { region: "tpci", label: "International (TPCi)" },
];

/**
 * The circuit a format belongs to. formats.json from before 2026-11-26 has no
 * region; every format in it that predates TPCi support is JP, so a missing
 * region means "jp". Do not infer the region from the slug.
 */
export function formatRegion(format: FormatInfo): FormatRegion {
  return format.region ?? "jp";
}

/**
 * Split formats by circuit: Japan City League first, then TPCi. Each group
 * keeps the input order (see sortFormats). Circuits with no formats are left out.
 */
export function groupFormatsByRegion(formats: FormatInfo[]): FormatRegionGroup[] {
  return REGIONS.map(({ region, label }) => ({
    region,
    label,
    formats: formats.filter((f) => formatRegion(f) === region),
  })).filter((g) => g.formats.length > 0);
}
