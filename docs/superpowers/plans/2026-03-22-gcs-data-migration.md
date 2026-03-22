# GCS Data Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move generated JSON data from git-committed files to GCS, reducing repo size by ~80MB and eliminating accidental deletion regressions.

**Architecture:** Cloud Build tars exported JSON, uploads to GCS (`gs://tcg-scout-data/`), generates a signed URL, and commits a lightweight manifest to git. Vercel prebuild downloads the tarball via signed URL, extracts it to `web/public/data/`, and Next.js builds against it. Data remains baked at build time (no client-side fetching).

**Tech Stack:** GCS (gsutil/gcloud), Cloud Build, Node.js (prebuild), Vercel static export

---

### Task 1: Create the data manifest schema and prebuild downloader

The prebuild script needs to download data from GCS instead of expecting it in git. A `web/data-manifest.json` file (committed to git) tells prebuild where to fetch data.

**Files:**
- Create: `web/data-manifest.json`
- Modify: `web/scripts/prebuild.mjs`
- Modify: `web/scripts/__tests__/prebuild.test.mjs`

- [ ] **Step 1: Create data-manifest.json**

```json
{
  "version": 1,
  "archives": [
    {
      "url": "",
      "sha256": "",
      "created_at": ""
    }
  ]
}
```

This is a placeholder. Cloud Build will overwrite it with a real signed URL on each scrape run. When `url` is empty, prebuild falls back to checking for local data (backward compatible for local dev).

- [ ] **Step 2: Rewrite prebuild.mjs to download from GCS**

Replace `web/scripts/prebuild.mjs` with a version that:
1. Reads `data-manifest.json`
2. If a URL is present and `web/public/data/` is empty or missing, downloads the tarball
3. Extracts to `web/public/data/`
4. Runs the existing validation checks
5. If no URL (local dev), checks for existing data on disk as before

```javascript
#!/usr/bin/env node
/**
 * Prebuild step: ensure JSON data is available for Next.js build.
 *
 * In CI (Vercel): downloads data tarball from GCS via signed URL in data-manifest.json.
 * In local dev: expects data already on disk from `python cli.py export-web`.
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

function shouldDownload() {
  // If data already exists on disk (local dev or git-committed), skip download
  const formatsPath = path.join(DATA_DIR, "formats.json");
  if (fs.existsSync(formatsPath)) return false;

  // Check manifest for a download URL
  if (!fs.existsSync(MANIFEST_PATH)) return false;
  const manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, "utf-8"));
  const archive = manifest.archives?.[0];
  return archive?.url?.length > 0;
}

async function downloadAndExtract() {
  const manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, "utf-8"));
  const archive = manifest.archives[0];
  const url = archive.url;
  const expectedHash = archive.sha256;

  console.log("prebuild: Downloading data from GCS...");
  const tarPath = path.join(ROOT, ".data-download.tar.gz");

  // Download using curl (available on all Vercel build images)
  execSync(`curl -fsSL -o "${tarPath}" "${url}"`, { stdio: "inherit" });

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

  // Extract
  fs.mkdirSync(DATA_DIR, { recursive: true });
  execSync(`tar -xzf "${tarPath}" -C "${DATA_DIR}"`, { stdio: "inherit" });
  fs.unlinkSync(tarPath);
  console.log("prebuild: Data extracted");
}

// --- Validation logic ---

function validate() {
  const formatsPath = path.join(DATA_DIR, "formats.json");
  if (!fs.existsSync(formatsPath)) {
    console.error(
      "prebuild: FATAL - No data found at public/data/formats.json.\n" +
        "  In CI: check data-manifest.json has a valid URL.\n" +
        "  Locally: run python cli.py --format <format> export-web",
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
```

- [ ] **Step 3: Update prebuild test**

Update `web/scripts/__tests__/prebuild.test.mjs`:

```javascript
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { execSync } from "child_process";
import fs from "fs";
import path from "path";
import os from "os";

describe("prebuild", () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "prebuild-test-"));
    fs.mkdirSync(path.join(tmpDir, "public", "data"), { recursive: true });
    const scriptsDir = path.join(tmpDir, "scripts");
    fs.mkdirSync(scriptsDir, { recursive: true });
    fs.copyFileSync(
      path.resolve(import.meta.dirname, "..", "prebuild.mjs"),
      path.join(scriptsDir, "prebuild.mjs"),
    );
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("exits 0 when formats.json exists with valid data", () => {
    fs.writeFileSync(path.join(tmpDir, "public", "data", "formats.json"), "[]");
    const result = execSync(`node ${path.join(tmpDir, "scripts", "prebuild.mjs")}`, {
      encoding: "utf-8",
    });
    expect(result).toContain("format(s) validated");
  });

  it("exits 1 when formats.json is missing and no manifest", () => {
    // Remove the data dir contents so formats.json doesn't exist
    fs.rmSync(path.join(tmpDir, "public", "data"), { recursive: true, force: true });
    fs.mkdirSync(path.join(tmpDir, "public", "data"), { recursive: true });
    let exitCode;
    let stderr;
    try {
      execSync(`node ${path.join(tmpDir, "scripts", "prebuild.mjs")}`, {
        encoding: "utf-8",
        stdio: ["pipe", "pipe", "pipe"],
      });
      exitCode = 0;
    } catch (err) {
      exitCode = err.status;
      stderr = err.stderr;
    }
    expect(exitCode).toBe(1);
    expect(stderr).toContain("FATAL");
  });

  it("skips download when data already exists on disk", () => {
    // Create formats.json and a manifest with a URL
    fs.writeFileSync(path.join(tmpDir, "public", "data", "formats.json"), "[]");
    fs.writeFileSync(
      path.join(tmpDir, "data-manifest.json"),
      JSON.stringify({ version: 1, archives: [{ url: "https://example.com/data.tar.gz", sha256: "", created_at: "" }] }),
    );
    const result = execSync(`node ${path.join(tmpDir, "scripts", "prebuild.mjs")}`, {
      encoding: "utf-8",
    });
    // Should validate without downloading since data exists
    expect(result).toContain("format(s) validated");
  });
});
```

- [ ] **Step 4: Run tests**

Run: `cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npx vitest run scripts/__tests__/prebuild.test.mjs`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add web/data-manifest.json web/scripts/prebuild.mjs web/scripts/__tests__/prebuild.test.mjs
git commit -m "feat: prebuild supports downloading data from GCS via signed URL"
```

---

### Task 2: Update Cloud Build to upload data to GCS

Replace the `push-to-github` step (which commits JSON to git) with steps that tar, upload, generate a signed URL, and commit a lightweight manifest.

**Files:**
- Modify: `cloudbuild-scrape.yaml`

- [ ] **Step 1: Replace the push-to-github step**

The new pipeline flow:
1. `restore-db-cache` (unchanged)
2. `scrape` (unchanged)
3. `validate` (unchanged)
4. `save-db-cache` (unchanged)
5. `upload-data` (NEW): tar the JSON data, upload to GCS, generate signed URL
6. `push-manifest` (NEW): write manifest with signed URL, commit, push

Replace the `push-to-github` step in `cloudbuild-scrape.yaml` with:

```yaml
  # Tar and upload exported JSON data to GCS
  - id: upload-data
    name: gcr.io/google.com/cloudsdktool/google-cloud-cli:slim
    entrypoint: bash
    args:
      - -c
      - |
        TIMESTAMP=$$(date -u +%Y%m%dT%H%M%SZ)
        TAR_FILE="data-$${TIMESTAMP}.tar.gz"
        GCS_PATH="gs://${_DATA_BUCKET}/$${TAR_FILE}"

        echo "Creating data archive..."
        tar -czf "/tmp/$${TAR_FILE}" -C web/public/data .

        echo "Uploading to $${GCS_PATH}..."
        gsutil cp "/tmp/$${TAR_FILE}" "$${GCS_PATH}"

        # Also upload as latest for convenience
        gsutil cp "$${GCS_PATH}" "gs://${_DATA_BUCKET}/data-latest.tar.gz"

        echo "Generating signed URL (valid 24h)..."
        SIGNED_URL=$$(gcloud storage sign-url "$${GCS_PATH}" --duration=24h --quiet 2>/dev/null | tail -1)

        # Compute SHA-256
        SHA256=$$(sha256sum "/tmp/$${TAR_FILE}" | cut -d' ' -f1)

        # Write manifest
        cat > web/data-manifest.json <<MANIFEST_EOF
        {
          "version": 1,
          "archives": [
            {
              "url": "$${SIGNED_URL}",
              "sha256": "$${SHA256}",
              "created_at": "$${TIMESTAMP}"
            }
          ]
        }
        MANIFEST_EOF

        echo "Manifest written. SHA-256: $${SHA256}"
    waitFor: ["save-db-cache"]

  # Commit manifest and push (lightweight, no JSON data)
  - id: push-manifest
    name: gcr.io/cloud-builders/git
    entrypoint: bash
    secretEnv: ["GITHUB_TOKEN"]
    args:
      - -c
      - |
        git config user.name "cloud-build[bot]"
        git config user.email "cloud-build[bot]@scout.trainerlab.io"
        git remote set-url origin "https://x-access-token:$$GITHUB_TOKEN@github.com/dtsong/tcg-scout.git"
        git add web/data-manifest.json
        git diff --cached --quiet && { echo "No manifest changes"; exit 0; }
        git commit -m "data: daily scrape $$(date -u +%Y-%m-%d)"
        git push origin HEAD:main
    waitFor: ["upload-data"]
```

Add the `_DATA_BUCKET` substitution:

```yaml
substitutions:
  _CACHE_BUCKET: tcg-scout-cache
  _DATA_BUCKET: tcg-scout-data
```

- [ ] **Step 2: Verify the YAML is valid**

Run: `python -c "import yaml; yaml.safe_load(open('cloudbuild-scrape.yaml'))" && echo "YAML valid"`
Expected: "YAML valid"

- [ ] **Step 3: Commit**

```bash
git add cloudbuild-scrape.yaml
git commit -m "feat: Cloud Build uploads data to GCS instead of committing to git"
```

---

### Task 3: Remove JSON data from git tracking

Now that data will come from GCS, remove the committed JSON files from git and add `web/public/data/` to `.gitignore`. Keep the manifest tracked.

**Files:**
- Modify: `.gitignore`
- Remove from git: `web/public/data/` (but keep on disk for local dev)

- [ ] **Step 1: Add web/public/data/ to .gitignore**

Add to `.gitignore` under the `# Data` section:

```
# Exported JSON data (fetched from GCS at build time)
web/public/data/
# Keep the manifest tracked
!web/data-manifest.json
```

- [ ] **Step 2: Remove data files from git tracking (keep on disk)**

```bash
git rm -r --cached web/public/data/
```

This removes the files from git's index but leaves them on disk so local dev still works.

- [ ] **Step 3: Verify local data still exists**

```bash
ls web/public/data/formats.json && echo "Local data preserved"
```

- [ ] **Step 4: Run the full build to verify nothing broke**

```bash
cd web && source ~/.nvm/nvm.sh && nvm use default --silent && npm run build
```
Expected: Build succeeds (data still on disk, just not in git)

- [ ] **Step 5: Commit**

```bash
git add .gitignore
git commit -m "chore: remove JSON data from git, will be fetched from GCS at build time

Data files (80MB, 1882 JSON files) are now gitignored.
Cloud Build uploads to GCS and commits a manifest with a signed URL.
Vercel prebuild downloads and extracts data before building.
Local dev: run 'python cli.py --format <format> export-web' to generate data."
```

---

### Task 4: Set up the GCS bucket for data storage

Create (or verify) the `gs://tcg-scout-data` bucket with appropriate settings.

**Files:**
- No code changes. Infrastructure setup.

- [ ] **Step 1: Verify/create the bucket**

```bash
gcloud storage buckets describe gs://tcg-scout-data 2>/dev/null || \
  gcloud storage buckets create gs://tcg-scout-data --location=us-central1 --uniform-bucket-level-access
```

- [ ] **Step 2: Grant the Cloud Build service account access**

The Cloud Build service account needs `storage.objectAdmin` on the data bucket (to upload and sign URLs):

```bash
PROJECT_ID=$(gcloud config get-value project)
CB_SA="${PROJECT_ID}@cloudbuild.gserviceaccount.com"
gcloud storage buckets add-iam-policy-binding gs://tcg-scout-data \
  --member="serviceAccount:${CB_SA}" \
  --role="roles/storage.objectAdmin"
```

For signed URL generation, the service account also needs `iam.serviceAccountTokenCreator` on itself:

```bash
gcloud iam service-accounts add-iam-policy-binding "${CB_SA}" \
  --member="serviceAccount:${CB_SA}" \
  --role="roles/iam.serviceAccountTokenCreator"
```

- [ ] **Step 3: Do a manual test upload and sign**

```bash
echo "test" > /tmp/test-upload.txt
gsutil cp /tmp/test-upload.txt gs://tcg-scout-data/test-upload.txt
gcloud storage sign-url gs://tcg-scout-data/test-upload.txt --duration=1h
gsutil rm gs://tcg-scout-data/test-upload.txt
```

Expected: Signed URL is generated and accessible

---

### Task 5: End-to-end test with a manual pipeline run

Before relying on the daily cron, do a manual test of the full pipeline.

- [ ] **Step 1: Run the local export and create a test archive**

```bash
python cli.py --format ninja-spinner export-web --strict
tar -czf /tmp/data-test.tar.gz -C web/public/data .
echo "Archive size: $(du -h /tmp/data-test.tar.gz | cut -f1)"
```

- [ ] **Step 2: Upload and generate a signed URL locally**

```bash
gsutil cp /tmp/data-test.tar.gz gs://tcg-scout-data/data-test.tar.gz
SIGNED_URL=$(gcloud storage sign-url gs://tcg-scout-data/data-test.tar.gz --duration=1h --quiet | tail -1)
SHA256=$(sha256sum /tmp/data-test.tar.gz | cut -d' ' -f1)
echo "URL: ${SIGNED_URL}"
echo "SHA: ${SHA256}"
```

- [ ] **Step 3: Test the prebuild download flow**

```bash
# Temporarily move data aside
mv web/public/data web/public/data-backup

# Write a test manifest
cat > web/data-manifest.json <<EOF
{
  "version": 1,
  "archives": [
    {
      "url": "${SIGNED_URL}",
      "sha256": "${SHA256}",
      "created_at": "$(date -u +%Y%m%dT%H%M%SZ)"
    }
  ]
}
EOF

# Run prebuild
cd web && source ~/.nvm/nvm.sh && nvm use default --silent && node scripts/prebuild.mjs

# Verify data was downloaded and extracted
ls public/data/formats.json && echo "SUCCESS: Data downloaded and extracted"

# Build
npm run build && echo "SUCCESS: Build completed"
```

- [ ] **Step 4: Restore local data**

```bash
rm -rf web/public/data
mv web/public/data-backup web/public/data
```

- [ ] **Step 5: Trigger a Cloud Build run to test the full pipeline**

```bash
gcloud builds submit --config=cloudbuild-scrape.yaml .
```

Monitor the build logs to verify:
- Data archive is created and uploaded
- Signed URL is generated
- Manifest is committed and pushed
- Vercel triggers a rebuild and the site is live

---

### Task 6: Update documentation

**Files:**
- Modify: `CLAUDE.md` (update data flow section)

- [ ] **Step 1: Update CLAUDE.md data flow**

Update the Architecture > Data Flow section:

```
### Data Flow

\```
Scrapers -> SQLite -> compute_meta_snapshot -> json_export -> GCS tarball -> Vercel prebuild -> Next.js SSG
\```

Cloud Build uploads exported JSON as a tarball to `gs://tcg-scout-data/`.
Vercel prebuild downloads via signed URL in `web/data-manifest.json`.
All frontend data is static JSON read at build time via `fs.readFileSync`. No runtime API calls.

For local development, run `python cli.py --format <format> export-web` to generate data on disk.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update data flow to reflect GCS migration"
```

---

## Verification

After all tasks are complete:

1. **Local dev still works**: `python cli.py --format ninja-spinner export-web && cd web && npm run build`
2. **Prebuild download works**: Remove `web/public/data/`, set manifest URL, run `node scripts/prebuild.mjs`
3. **Cloud Build pipeline**: Trigger manually, verify upload + signed URL + manifest commit
4. **Vercel deploys**: Verify site builds and serves correctly from GCS-fetched data
5. **Repo size**: `git count-objects -vH` shows reduced size after data removal

## Rollback

If issues arise:
1. Remove `web/public/data/` from `.gitignore`
2. Re-export and commit data: `python cli.py --format <format> export-web && git add web/public/data/ && git commit`
3. Revert `cloudbuild-scrape.yaml` to the git-commit version
4. The prebuild script is backward-compatible (skips download if data exists on disk)
