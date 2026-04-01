#!/usr/bin/env node
import fs from "fs";
import path from "path";

const ROOT = path.resolve(import.meta.dirname, "..");
const OUT_DIR = path.join(ROOT, "out");
const MANIFEST_PATH = path.join(ROOT, "test-route-manifest.json");

if (!fs.existsSync(OUT_DIR)) {
  console.error("validate-export: FATAL - out/ was not generated.");
  process.exit(1);
}

if (!fs.existsSync(MANIFEST_PATH)) {
  console.error("validate-export: FATAL - test-route-manifest.json is missing.");
  process.exit(1);
}

const manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, "utf-8"));

function routeToHtmlPath(routePath) {
  if (routePath === "/") return [path.join(OUT_DIR, "index.html")];
  const stripped = routePath.replace(/^\/+/, "");
  return [
    path.join(OUT_DIR, stripped, "index.html"),
    path.join(OUT_DIR, `${stripped}.html`),
  ];
}

const missingRoutes = manifest.broadRoutes
  .map((route) => route.path)
  .filter((routePath) => !routeToHtmlPath(routePath).some((candidate) => fs.existsSync(candidate)));

if (missingRoutes.length > 0) {
  console.error("validate-export: FATAL - missing exported routes:");
  for (const routePath of missingRoutes) {
    console.error(`  ${routePath}`);
  }
  process.exit(1);
}

console.log(`validate-export: verified ${manifest.broadRoutes.length} exported routes`);
