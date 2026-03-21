import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import fs from "fs";
import path from "path";
import os from "os";

// Mock @vercel/blob
vi.mock("@vercel/blob", () => ({
  put: vi.fn(async (pathname) => ({
    url: `https://test.blob.vercel-storage.com/${pathname}`,
    downloadUrl: `https://test.blob.vercel-storage.com/${pathname}?download=1`,
    pathname,
  })),
}));

describe("blob-upload: collectFiles", () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "blob-upload-test-"));
    // Create test file structure
    fs.mkdirSync(path.join(tmpDir, "nihil-zero", "archetypes"), { recursive: true });
    fs.mkdirSync(path.join(tmpDir, "images"), { recursive: true });
    fs.writeFileSync(path.join(tmpDir, "formats.json"), '[]');
    fs.writeFileSync(path.join(tmpDir, "nihil-zero", "meta.json"), '{}');
    fs.writeFileSync(path.join(tmpDir, "nihil-zero", "archetypes", "charizard.json"), '{}');
    fs.writeFileSync(path.join(tmpDir, "images", "card.png"), 'binary');
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("collects JSON files recursively", () => {
    const files = collectFilesFrom(tmpDir);
    const paths = files.map((f) => f.blobPath).sort();
    expect(paths).toEqual([
      "formats.json",
      "nihil-zero/archetypes/charizard.json",
      "nihil-zero/meta.json",
    ]);
  });

  it("skips images directory", () => {
    const files = collectFilesFrom(tmpDir);
    const paths = files.map((f) => f.blobPath);
    expect(paths).not.toContain("images/card.png");
  });

  it("skips non-JSON files", () => {
    fs.writeFileSync(path.join(tmpDir, "readme.md"), "# test");
    const files = collectFilesFrom(tmpDir);
    const paths = files.map((f) => f.blobPath);
    expect(paths).not.toContain("readme.md");
  });
});

// Inline the function for testing since the script uses top-level execution
function collectFilesFrom(dir, base = dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "images") continue;
      files.push(...collectFilesFrom(full, base));
    } else if (entry.name.endsWith(".json")) {
      files.push({
        localPath: full,
        blobPath: path.relative(base, full),
      });
    }
  }
  return files;
}
