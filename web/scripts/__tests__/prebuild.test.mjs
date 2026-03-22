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
    fs.writeFileSync(path.join(tmpDir, "public", "data", "formats.json"), "[]");
    fs.writeFileSync(
      path.join(tmpDir, "data-manifest.json"),
      JSON.stringify({
        version: 1,
        archives: [{ url: "https://example.com/data.tar.gz", sha256: "", created_at: "" }],
      }),
    );
    const result = execSync(`node ${path.join(tmpDir, "scripts", "prebuild.mjs")}`, {
      encoding: "utf-8",
    });
    expect(result).toContain("format(s) validated");
  });
});
