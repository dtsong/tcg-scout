#!/usr/bin/env node
/**
 * Prebuild step: verify that JSON data exists on disk.
 * Data is committed to git by Cloud Build, so it's available at checkout
 * on both Vercel and local development.
 */
import fs from "fs";
import path from "path";

const DATA_DIR = path.resolve(import.meta.dirname, "..", "public", "data");
const formatsPath = path.join(DATA_DIR, "formats.json");

if (fs.existsSync(formatsPath)) {
  console.log("prebuild: Data found");
} else {
  console.error(
    "prebuild: FATAL - No data found at public/data/formats.json.\n" +
      "  Data should be committed to git by Cloud Build.\n" +
      "  For local development, run: python cli.py --format <format> export-web",
  );
  process.exit(1);
}
