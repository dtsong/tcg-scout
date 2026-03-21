#!/usr/bin/env node
/**
 * Prebuild step: download data from Vercel Blob Store if BLOB_READ_WRITE_TOKEN
 * is set (i.e., running on Vercel). Skips gracefully for local development
 * where data already exists on disk from the Python export pipeline.
 */
import fs from "fs";
import path from "path";

const DATA_DIR = path.resolve(import.meta.dirname, "..", "public", "data");

if (!process.env.BLOB_READ_WRITE_TOKEN) {
  // Local development -- check that data exists
  const formatsPath = path.join(DATA_DIR, "formats.json");
  if (fs.existsSync(formatsPath)) {
    console.log("prebuild: Local data found, skipping blob download");
  } else {
    console.warn(
      "prebuild: No BLOB_READ_WRITE_TOKEN and no local data found.\n" +
        "  Run the Python export pipeline first, or set BLOB_READ_WRITE_TOKEN to download from Blob Store.",
    );
  }
  process.exit(0);
}

// On Vercel (or when token is set) -- download from Blob Store
console.log("prebuild: Downloading data from Vercel Blob Store...");
const { execSync } = await import("child_process");
execSync("node scripts/blob-download.mjs", {
  stdio: "inherit",
  cwd: path.resolve(import.meta.dirname, ".."),
  env: process.env,
});
