#!/usr/bin/env node
/**
 * Upload all JSON files from web/public/data/ to Vercel Blob Store.
 *
 * Usage:
 *   BLOB_READ_WRITE_TOKEN=<token> node scripts/blob-upload.mjs
 *   BLOB_READ_WRITE_TOKEN=<token> node scripts/blob-upload.mjs --prefix nihil-zero
 *
 * Options:
 *   --prefix <format>   Only upload files under a specific format directory
 *   --dry-run           List files that would be uploaded without uploading
 */
import { put, list, del } from "@vercel/blob";
import fs from "fs";
import path from "path";

const DATA_DIR = path.resolve(import.meta.dirname, "..", "public", "data");

function collectFiles(dir, base = dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      // Skip images directory -- served separately
      if (entry.name === "images") continue;
      files.push(...collectFiles(full, base));
    } else if (entry.name.endsWith(".json")) {
      files.push({
        localPath: full,
        blobPath: path.relative(base, full),
      });
    }
  }
  return files;
}

async function upload() {
  const args = process.argv.slice(2);
  const dryRun = args.includes("--dry-run");
  const prefixIdx = args.indexOf("--prefix");
  const prefix = prefixIdx !== -1 ? args[prefixIdx + 1] : null;

  if (!process.env.BLOB_READ_WRITE_TOKEN) {
    console.error("Error: BLOB_READ_WRITE_TOKEN environment variable is required");
    process.exit(1);
  }

  if (!fs.existsSync(DATA_DIR)) {
    console.error(`Error: Data directory not found: ${DATA_DIR}`);
    process.exit(1);
  }

  const sourceDir = prefix ? path.join(DATA_DIR, prefix) : DATA_DIR;
  if (!fs.existsSync(sourceDir)) {
    console.error(`Error: Source directory not found: ${sourceDir}`);
    process.exit(1);
  }

  const files = collectFiles(sourceDir, DATA_DIR);
  console.log(`Found ${files.length} JSON files to upload${prefix ? ` (prefix: ${prefix})` : ""}`);

  if (dryRun) {
    for (const f of files) {
      console.log(`  [dry-run] ${f.blobPath} (${(fs.statSync(f.localPath).size / 1024).toFixed(1)} KB)`);
    }
    return;
  }

  let uploaded = 0;
  let failed = 0;
  const batchSize = 5;
  const maxRetries = 3;

  async function uploadFile(f, attempt = 1) {
    try {
      const content = fs.readFileSync(f.localPath);
      const blob = await put(f.blobPath, content, {
        access: "public",
        addRandomSuffix: false,
        allowOverwrite: true,
        contentType: "application/json",
      });
      return { path: f.blobPath, url: blob.url };
    } catch (err) {
      if (attempt < maxRetries && /too many requests/i.test(err.message)) {
        const delay = attempt * 2000;
        await new Promise((r) => setTimeout(r, delay));
        return uploadFile(f, attempt + 1);
      }
      throw err;
    }
  }

  for (let i = 0; i < files.length; i += batchSize) {
    const batch = files.slice(i, i + batchSize);
    const results = await Promise.allSettled(batch.map((f) => uploadFile(f)));

    for (const result of results) {
      if (result.status === "fulfilled") {
        uploaded++;
      } else {
        failed++;
        console.error(`  Failed: ${result.reason.message}`);
      }
    }

    const pct = Math.round(((i + batch.length) / files.length) * 100);
    process.stdout.write(`\r  Uploaded ${uploaded}/${files.length} (${pct}%)`);
  }

  console.log(`\nDone: ${uploaded} uploaded, ${failed} failed`);
  if (failed > 0) process.exit(1);
}

upload().catch((err) => {
  console.error("Upload failed:", err.message);
  process.exit(1);
});
