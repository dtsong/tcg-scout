#!/usr/bin/env node
/**
 * Prebuild step: ensure JSON data is available for Next.js build.
 *
 * In CI (Vercel): downloads data tarball from GCS via signed URL in data-manifest.json.
 * In local dev: expects data already on disk from `uv run scout export-web`.
 */
import fs from "fs";
import path from "path";
import { execSync } from "child_process";
import { createHash } from "crypto";

const ROOT = path.resolve(import.meta.dirname, "..");
const DATA_DIR = path.join(ROOT, "public", "data");
const MANIFEST_PATH = path.join(ROOT, "data-manifest.json");

const REQUIRED_FILES = [
  "meta.json",
  "buylist.json",
  "staples.json",
  "flex.json",
  "trends.json",
  "winning-edge.json",
];

// --- Download logic ---

const HASH_FILE = path.join(DATA_DIR, ".manifest-sha256");

function shouldDownload() {
  // Check manifest for a download URL
  if (!fs.existsSync(MANIFEST_PATH)) return false;
  const manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, "utf-8"));
  const archive = manifest.archives?.[0];
  if (!archive?.url?.length) return false;

  // In local dev, data already on disk from export-web — skip unless hash changed
  const formatsPath = path.join(DATA_DIR, "formats.json");
  if (!fs.existsSync(formatsPath)) return true;

  // Re-download if manifest SHA changed (new data available)
  if (archive.sha256 && fs.existsSync(HASH_FILE)) {
    const cached = fs.readFileSync(HASH_FILE, "utf-8").trim();
    if (cached === archive.sha256) return false;
  }

  // In CI (Vercel), always download if we can't verify the hash matches
  return !!process.env.VERCEL;
}

async function downloadAndExtract() {
  const manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, "utf-8"));
  const archive = manifest.archives[0];
  const url = archive.url;
  const expectedHash = archive.sha256;

  console.log("prebuild: Downloading data from GCS...");
  const tarPath = path.join(ROOT, ".data-download.tar.gz");

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const buf = Buffer.from(await res.arrayBuffer());
    fs.writeFileSync(tarPath, buf);
  } catch (err) {
    console.error(
      "prebuild: FATAL - Failed to download data archive.\n" +
        `  ${err.message}\n` +
        "  Check that the GCS bucket is publicly readable and Cloud Build is running.",
    );
    process.exit(1);
  }

  // Verify SHA-256 if provided
  if (expectedHash) {
    const fileBuffer = fs.readFileSync(tarPath);
    const actualHash = createHash("sha256").update(fileBuffer).digest("hex");
    if (actualHash !== expectedHash) {
      fs.unlinkSync(tarPath);
      console.error(
        `prebuild: FATAL - SHA-256 mismatch.\n` +
          `  Expected: ${expectedHash}\n` +
          `  Actual:   ${actualHash}`,
      );
      process.exit(1);
    }
    console.log("prebuild: SHA-256 verified");
  }

  // Wipe stale data before extracting fresh archive
  if (fs.existsSync(DATA_DIR)) {
    fs.rmSync(DATA_DIR, { recursive: true });
  }

  // Extract
  fs.mkdirSync(DATA_DIR, { recursive: true });
  execSync(`tar -xzf "${tarPath}" -C "${DATA_DIR}"`, { stdio: "inherit" });
  fs.unlinkSync(tarPath);

  // Clean macOS resource fork files that break Next.js SSG
  execSync(`find "${DATA_DIR}" -name '._*' -delete 2>/dev/null || true`);

  // Record extracted archive hash for cache invalidation
  if (expectedHash) {
    fs.writeFileSync(path.join(DATA_DIR, ".manifest-sha256"), expectedHash);
  }

  console.log("prebuild: Data extracted");
}

// --- Validation logic ---

function validate() {
  const formatsPath = path.join(DATA_DIR, "formats.json");
  if (!fs.existsSync(formatsPath)) {
    console.error(
      "prebuild: FATAL - No data found at public/data/formats.json.\n" +
        "  In CI: check data-manifest.json has a valid URL.\n" +
        "  Locally: run uv run scout --format <format> export-web",
    );
    process.exit(1);
  }

  const formats = JSON.parse(fs.readFileSync(formatsPath, "utf-8"));
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

  console.log(
    `prebuild: All ${formats.filter((f) => f.status !== "upcoming").length} format(s) validated`,
  );
}

// --- Main ---

if (shouldDownload()) {
  await downloadAndExtract();
}
validate();
const testManifestScript = path.join(import.meta.dirname, "generate-test-manifest.mjs");
if (fs.existsSync(testManifestScript)) {
  execSync(`node "${testManifestScript}"`, {
    cwd: ROOT,
    stdio: "inherit",
  });
}
