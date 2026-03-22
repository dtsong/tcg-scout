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
    // Copy the prebuild script to the tmp dir so import.meta.dirname resolves to tmpDir/scripts
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

  it("exits 0 when formats.json exists", () => {
    fs.writeFileSync(path.join(tmpDir, "public", "data", "formats.json"), "[]");
    const result = execSync(`node ${path.join(tmpDir, "scripts", "prebuild.mjs")}`, {
      encoding: "utf-8",
    });
    expect(result).toContain("Data found");
  });

  it("exits 1 when formats.json is missing", () => {
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
});
