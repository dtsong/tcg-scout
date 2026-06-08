import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

const DATA_DIR = path.join(process.cwd(), "public", "data");
const FORMATS_PATH = path.join(DATA_DIR, "formats.json");

function readJson<T>(...segments: string[]): T {
  return JSON.parse(fs.readFileSync(path.join(DATA_DIR, ...segments), "utf-8")) as T;
}

const hasData = fs.existsSync(FORMATS_PATH);

describe.skipIf(!hasData)("public data contracts", () => {
  const formats = hasData
    ? readJson<Array<{ slug: string; status: string }>>("formats.json")
        .filter((format) => format.status !== "upcoming")
    : [];

  it("has required files for each shipped format", () => {
    for (const format of formats) {
      for (const filename of [
        "meta.json",
        "buylist.json",
        "staples.json",
        "flex.json",
        "trends.json",
        "winning-edge.json",
      ]) {
        expect(fs.existsSync(path.join(DATA_DIR, format.slug, filename)), `${format.slug}/${filename}`).toBe(true);
      }
    }
  });

  it("keeps meta and archetype detail files aligned", () => {
    for (const format of formats) {
      const meta = readJson<{
        deck_count: number;
        archetypes: Array<{ slug: string; archetype: string; meta_share: number; sprite_filenames?: string[] }>;
      }>(format.slug, "meta.json");

      expect(meta.deck_count, `${format.slug} deck_count`).toBeGreaterThan(0);
      expect(meta.archetypes.length, `${format.slug} archetypes`).toBeGreaterThan(0);

      for (const archetype of meta.archetypes) {
        const detailPath = path.join(DATA_DIR, format.slug, "archetypes", `${archetype.slug}.json`);
        expect(fs.existsSync(detailPath), detailPath).toBe(true);

        const detail = JSON.parse(fs.readFileSync(detailPath, "utf-8")) as {
          slug: string;
          archetype: string;
          meta_share: number;
          sprite_filenames?: string[];
        };

        expect(detail.slug).toBe(archetype.slug);
        expect(detail.archetype).toBe(archetype.archetype);
        expect(detail.meta_share).toBe(archetype.meta_share);

        for (const spriteFilename of detail.sprite_filenames ?? []) {
          expect(
            fs.existsSync(path.join(DATA_DIR, "images", "sprites", spriteFilename)),
            `${format.slug}:${spriteFilename}`,
          ).toBe(true);
        }
      }
    }
  });

  it("keeps card index and card detail files aligned", () => {
    for (const format of formats) {
      const indexPath = path.join(DATA_DIR, format.slug, "cards", "index.json");
      if (!fs.existsSync(indexPath)) continue;

      const cards = JSON.parse(fs.readFileSync(indexPath, "utf-8")) as Array<{
        card_slug: string;
        card_name: string;
        usage_pct: number;
      }>;

      expect(cards.length, `${format.slug} card index`).toBeGreaterThan(0);

      for (const card of cards.slice(0, 50)) {
        const detailPath = path.join(DATA_DIR, format.slug, "cards", `${card.card_slug}.json`);
        expect(fs.existsSync(detailPath), detailPath).toBe(true);

        const detail = JSON.parse(fs.readFileSync(detailPath, "utf-8")) as {
          card_slug: string;
          card_name: string;
          usage_pct: number;
        };

        expect(detail.card_slug).toBe(card.card_slug);
        expect(detail.card_name).toBe(card.card_name);
        expect(detail.usage_pct).toBe(card.usage_pct);
      }
    }
  });
});
