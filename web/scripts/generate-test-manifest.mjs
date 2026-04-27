#!/usr/bin/env node
import fs from "fs";
import path from "path";

const ROOT = path.resolve(import.meta.dirname, "..");
const DATA_DIR = path.join(ROOT, "public", "data");
const OUTPUT_PATH = path.join(ROOT, "test-route-manifest.json");

function readJson(relativePath) {
  return JSON.parse(fs.readFileSync(path.join(DATA_DIR, relativePath), "utf-8"));
}

function exists(relativePath) {
  return fs.existsSync(path.join(DATA_DIR, relativePath));
}

function uniqueByPath(routes) {
  const seen = new Set();
  return routes.filter((route) => {
    if (seen.has(route.path)) return false;
    seen.add(route.path);
    return true;
  });
}

const formats = readJson("formats.json")
  .filter((format) => format.status !== "upcoming")
  .map((format) => {
    const slug = format.slug;
    const meta = readJson(`${slug}/meta.json`);
    const cards = exists(`${slug}/cards/index.json`) ? readJson(`${slug}/cards/index.json`) : [];
    const optimal60 = exists(`${slug}/optimal-60/index.json`) ? readJson(`${slug}/optimal-60/index.json`) : null;
    const reportExists = exists(`${slug}/report.json`);
    const forecastExists = exists(`${slug}/tech-forecast.json`);
    const matchupExists = exists(`${slug}/matchup.json`);
    const cardAnalysisExists = exists(`${slug}/card-analysis.json`);
    const playersExists = exists(`${slug}/players/index.json`);
    const shiftsExists = exists(`${slug}/meta-evolution.json`);
    const tournamentsExists = exists(`${slug}/timeline.json`);
    const archetypeReportExists = meta.archetypes.some((arch) =>
      exists(`${slug}/archetype-reports/${arch.slug}.json`),
    );

    return {
      slug,
      status: format.status,
      topArchetypeSlug: meta.archetypes[0]?.slug ?? null,
      topCardSlug: cards[0]?.card_slug ?? null,
      optimal60Slug: optimal60?.archetypes?.[0]?.slug ?? null,
      routeFlags: {
        report: reportExists,
        forecast: forecastExists,
        matchups: matchupExists,
        cardAnalysis: cardAnalysisExists,
        players: playersExists,
        shifts: shiftsExists,
        tournaments: tournamentsExists,
        optimal60: Boolean(optimal60?.archetypes?.length),
        archetypeReport: archetypeReportExists,
      },
    };
  });

const broadRoutes = [
  { path: "/", kind: "landing" },
  { path: "/start", kind: "landing" },
  { path: "/guide", kind: "landing" },
  { path: "/blog", kind: "landing" },
];

for (const format of formats) {
  const prefix = `/${format.slug}`;
  broadRoutes.push({ path: prefix, kind: "format-dashboard", format: format.slug });
  broadRoutes.push({ path: `${prefix}/archetypes`, kind: "format-index", format: format.slug });
  broadRoutes.push({ path: `${prefix}/buylist`, kind: "format-index", format: format.slug });
  broadRoutes.push({ path: `${prefix}/cards`, kind: "format-index", format: format.slug });
  broadRoutes.push({ path: `${prefix}/guide`, kind: "format-index", format: format.slug });
  broadRoutes.push({ path: `${prefix}/trends`, kind: "format-index", format: format.slug });

  if (format.routeFlags.cardAnalysis) {
    broadRoutes.push({ path: `${prefix}/card-analysis`, kind: "format-index", format: format.slug });
  }
  if (format.routeFlags.report) {
    broadRoutes.push({ path: `${prefix}/report`, kind: "format-index", format: format.slug });
  }
  if (format.routeFlags.forecast) {
    broadRoutes.push({ path: `${prefix}/forecast`, kind: "format-index", format: format.slug });
  }
  if (format.routeFlags.matchups) {
    broadRoutes.push({ path: `${prefix}/matchups`, kind: "format-index", format: format.slug });
  }
  if (format.routeFlags.players) {
    broadRoutes.push({ path: `${prefix}/players`, kind: "format-index", format: format.slug });
  }
  if (format.routeFlags.shifts) {
    broadRoutes.push({ path: `${prefix}/shifts`, kind: "format-index", format: format.slug });
    broadRoutes.push({ path: `${prefix}/meta-ev`, kind: "format-index", format: format.slug });
  }
  if (format.routeFlags.tournaments) {
    broadRoutes.push({ path: `${prefix}/tournaments`, kind: "format-index", format: format.slug });
    broadRoutes.push({ path: `${prefix}/champions`, kind: "format-index", format: format.slug });
  }
  if (format.routeFlags.optimal60) {
    broadRoutes.push({ path: `${prefix}/optimal-60`, kind: "format-index", format: format.slug });
  }
  if (format.topArchetypeSlug) {
    broadRoutes.push({
      path: `${prefix}/archetypes/${format.topArchetypeSlug}`,
      kind: "archetype-detail",
      format: format.slug,
    });
    if (format.routeFlags.archetypeReport) {
      broadRoutes.push({
        path: `${prefix}/archetypes/${format.topArchetypeSlug}/report`,
        kind: "archetype-report",
        format: format.slug,
      });
    }
  }
  if (format.topCardSlug) {
    broadRoutes.push({
      path: `${prefix}/cards/${format.topCardSlug}`,
      kind: "card-detail",
      format: format.slug,
    });
  }
}

const manifest = {
  generatedAt: new Date().toISOString(),
  formats,
  broadRoutes: uniqueByPath(broadRoutes),
  // Visual snapshots only run against frozen formats. Active formats re-scrape
  // every few hours and drift every chart, count, and timestamp, which would
  // require regenerating baselines on every cron run. Layout/CSS regressions
  // surface on frozen routes since both formats share the same components.
  visualRoutes: uniqueByPath([
    { path: "/start", name: "start-desktop", viewport: { width: 1440, height: 900 } },
    ...formats
      .filter((format) => format.status === "frozen")
      .flatMap((format) => {
        const prefix = `/${format.slug}`;
        const routes = [
          { path: prefix, name: `${format.slug}-dashboard-desktop`, viewport: { width: 1440, height: 900 } },
          { path: `${prefix}/archetypes`, name: `${format.slug}-archetypes-desktop`, viewport: { width: 1440, height: 900 } },
        ];
        if (format.topArchetypeSlug) {
          routes.push({
            path: `${prefix}/archetypes/${format.topArchetypeSlug}`,
            name: `${format.slug}-archetype-detail-desktop`,
            viewport: { width: 1440, height: 900 },
          });
        }
        if (format.routeFlags.cardAnalysis) {
          routes.push({
            path: `${prefix}/card-analysis`,
            name: `${format.slug}-card-analysis-desktop`,
            viewport: { width: 1440, height: 900 },
          });
        }
        return routes;
      }),
  ]),
  performanceRoutes: uniqueByPath([
    ...formats.map((format) => ({
      path: `/${format.slug}`,
      budget: {
        lcpMs: 4000,
        domCompleteMs: 5000,
        totalBytes: 2_500_000,
        resourceCount: 200,
        imageCount: 80,
      },
    })),
    ...formats
      .filter((format) => format.routeFlags.cardAnalysis)
      .map((format) => ({
        path: `/${format.slug}/card-analysis`,
        budget: {
          lcpMs: 4500,
          domCompleteMs: 6000,
          totalBytes: 3_500_000,
          resourceCount: 260,
          imageCount: 120,
        },
      })),
    ...formats
      .filter((format) => format.topArchetypeSlug)
      .map((format) => ({
        path: `/${format.slug}/archetypes/${format.topArchetypeSlug}`,
        budget: {
          lcpMs: 4500,
          domCompleteMs: 6000,
          totalBytes: 3_500_000,
          resourceCount: 240,
          imageCount: 120,
        },
      })),
  ]),
};

fs.writeFileSync(OUTPUT_PATH, `${JSON.stringify(manifest, null, 2)}\n`);
console.log(`prebuild: Test manifest written to ${path.relative(ROOT, OUTPUT_PATH)}`);
