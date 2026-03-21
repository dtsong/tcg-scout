#!/usr/bin/env node
/**
 * Download all JSON files from Vercel Blob Store to web/public/data/.
 * Used as a prebuild step so data.ts can read from the filesystem as usual.
 *
 * Usage:
 *   BLOB_READ_WRITE_TOKEN=<token> node scripts/blob-download.mjs
 *   BLOB_READ_WRITE_TOKEN=<token> node scripts/blob-download.mjs --prefix nihil-zero
 *
 * Options:
 *   --prefix <format>   Only download files under a specific format directory
 *   --dry-run           List files that would be downloaded without downloading
 */
import { list } from "@vercel/blob";
import fs from "fs";
import path from "path";

const DATA_DIR = path.resolve(import.meta.dirname, "..", "public", "data");

async function listAllBlobs(prefix) {
  const blobs = [];
  let cursor;

  do {
    const result = await list({
      prefix: prefix || undefined,
      limit: 1000,
      cursor,
      token: process.env.BLOB_READ_WRITE_TOKEN,
    });
    blobs.push(...result.blobs);
    cursor = result.hasMore ? result.cursor : undefined;
  } while (cursor);

  return blobs;
}

async function download() {
  const args = process.argv.slice(2);
  const dryRun = args.includes("--dry-run");
  const prefixIdx = args.indexOf("--prefix");
  const prefix = prefixIdx !== -1 ? args[prefixIdx + 1] : null;

  if (!process.env.BLOB_READ_WRITE_TOKEN) {
    console.error("Error: BLOB_READ_WRITE_TOKEN environment variable is required");
    process.exit(1);
  }

  console.log("Listing blobs from Vercel Blob Store...");
  const blobs = await listAllBlobs(prefix);
  const jsonBlobs = blobs.filter((b) => b.pathname.endsWith(".json"));

  console.log(`Found ${jsonBlobs.length} JSON files${prefix ? ` (prefix: ${prefix})` : ""}`);

  if (dryRun) {
    for (const b of jsonBlobs) {
      console.log(`  [dry-run] ${b.pathname} (${(b.size / 1024).toFixed(1)} KB)`);
    }
    return;
  }

  let downloaded = 0;
  let failed = 0;
  const batchSize = 20;

  for (let i = 0; i < jsonBlobs.length; i += batchSize) {
    const batch = jsonBlobs.slice(i, i + batchSize);
    const results = await Promise.allSettled(
      batch.map(async (blob) => {
        const localPath = path.join(DATA_DIR, blob.pathname);
        const dir = path.dirname(localPath);
        fs.mkdirSync(dir, { recursive: true });

        const response = await fetch(blob.downloadUrl);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status} for ${blob.pathname}`);
        }
        const content = await response.text();
        fs.writeFileSync(localPath, content, "utf-8");
        return blob.pathname;
      }),
    );

    for (const result of results) {
      if (result.status === "fulfilled") {
        downloaded++;
      } else {
        failed++;
        console.error(`  Failed: ${result.reason.message}`);
      }
    }

    const pct = Math.round(((i + batch.length) / jsonBlobs.length) * 100);
    process.stdout.write(`\r  Downloaded ${downloaded}/${jsonBlobs.length} (${pct}%)`);
  }

  console.log(`\nDone: ${downloaded} downloaded, ${failed} failed`);
  if (failed > 0) process.exit(1);
}

download().catch((err) => {
  console.error("Download failed:", err.message);
  process.exit(1);
});
