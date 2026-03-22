#!/usr/bin/env node
/**
 * Prebuild step: verify JSON data exists and is complete for all formats.
 * Catches missing files before they become broken pages in production.
 */
import fs from "fs";
import path from "path";

const DATA_DIR = path.resolve(import.meta.dirname, "..", "public", "data");
const formatsPath = path.join(DATA_DIR, "formats.json");

if (!fs.existsSync(formatsPath)) {
  console.error(
    "prebuild: FATAL - No data found at public/data/formats.json.\n" +
      "  Data should be committed to git by Cloud Build.\n" +
      "  For local development, run: python cli.py --format <format> export-web",
  );
  process.exit(1);
}

const formats = JSON.parse(fs.readFileSync(formatsPath, "utf-8"));
const REQUIRED_FILES = [
  "meta.json",
  "buylist.json",
  "staples.json",
  "flex.json",
  "trends.json",
  "winning-edge.json",
];

let errors = 0;

for (const fmt of formats) {
  if (fmt.status === "upcoming") continue;

  const fmtDir = path.join(DATA_DIR, fmt.slug);
  for (const file of REQUIRED_FILES) {
    const filePath = path.join(fmtDir, file);
    if (!fs.existsSync(filePath)) {
      console.error(`prebuild: MISSING ${fmt.slug}/${file}`);
      errors++;
    }
  }

  // Check archetypes directory is non-empty
  const archDir = path.join(fmtDir, "archetypes");
  if (!fs.existsSync(archDir) || fs.readdirSync(archDir).length === 0) {
    console.error(`prebuild: MISSING ${fmt.slug}/archetypes/ (empty or absent)`);
    errors++;
  }
}

if (errors > 0) {
  console.error(`\nprebuild: FATAL - ${errors} missing file(s) detected. Aborting build.`);
  process.exit(1);
}

console.log(`prebuild: All ${formats.filter((f) => f.status !== "upcoming").length} format(s) validated`);
