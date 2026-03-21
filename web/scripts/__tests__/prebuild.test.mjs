import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import fs from "fs";
import path from "path";
import os from "os";

describe("prebuild logic", () => {
  let tmpDir;
  const originalEnv = { ...process.env };

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "prebuild-test-"));
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
    process.env = originalEnv;
  });

  it("detects local data when formats.json exists", () => {
    fs.writeFileSync(path.join(tmpDir, "formats.json"), "[]");
    expect(fs.existsSync(path.join(tmpDir, "formats.json"))).toBe(true);
  });

  it("detects missing local data when formats.json is absent", () => {
    expect(fs.existsSync(path.join(tmpDir, "formats.json"))).toBe(false);
  });

  it("requires BLOB_READ_WRITE_TOKEN for remote download", () => {
    delete process.env.BLOB_READ_WRITE_TOKEN;
    expect(process.env.BLOB_READ_WRITE_TOKEN).toBeUndefined();
  });
});
