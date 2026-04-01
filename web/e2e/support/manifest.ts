import fs from "fs";
import path from "path";

type RouteEntry = {
  path: string;
  kind?: string;
  format?: string;
};

type VisualRoute = {
  path: string;
  name: string;
  viewport: { width: number; height: number };
};

type PerformanceRoute = {
  path: string;
  budget: {
    lcpMs: number;
    domCompleteMs: number;
    totalBytes: number;
    resourceCount: number;
    imageCount: number;
  };
};

type RouteManifest = {
  broadRoutes: RouteEntry[];
  visualRoutes: VisualRoute[];
  performanceRoutes: PerformanceRoute[];
  formats: Array<{
    slug: string;
    topArchetypeSlug: string | null;
    topCardSlug: string | null;
  }>;
};

let cachedManifest: RouteManifest | null = null;

export function getRouteManifest(): RouteManifest {
  if (cachedManifest) return cachedManifest;

  const manifestPath = path.join(process.cwd(), "test-route-manifest.json");
  cachedManifest = JSON.parse(fs.readFileSync(manifestPath, "utf-8")) as RouteManifest;
  return cachedManifest;
}

export function getBroadRoutes(): RouteEntry[] {
  return getRouteManifest().broadRoutes;
}

export function getVisualRoutes(): VisualRoute[] {
  return getRouteManifest().visualRoutes;
}

export function getPerformanceRoutes(): PerformanceRoute[] {
  return getRouteManifest().performanceRoutes;
}
