import { expect, type Page } from "@playwright/test";

type NetworkRecorder = {
  failures: string[];
  dispose: () => void;
};

function shouldIgnoreNetworkFailure(urlString: string, resourceType: string, detail?: string) {
  const url = new URL(urlString);
  const isStaticHost = url.host === "localhost:3333" || url.host === "127.0.0.1:3333";

  if (url.pathname.startsWith("/_vercel/insights/")) {
    return true;
  }

  const isInternalRoutePrefetch =
    isStaticHost &&
    ["fetch", "xhr"].includes(resourceType) &&
    !pathHasExtension(url.pathname) &&
    !url.pathname.startsWith("/data/");

  if (isInternalRoutePrefetch) {
    return true;
  }

  if ((detail ?? "").includes("net::ERR_ABORTED") && isStaticHost) {
    return true;
  }

  return false;
}

function pathHasExtension(pathname: string) {
  return pathname.split("/").at(-1)?.includes(".") ?? false;
}

export async function preparePage(page: Page) {
  await page.addInitScript(() => {
    const installTestStyles = () => {
      if (document.getElementById("pw-test-styles")) return;
      const style = document.createElement("style");
      style.id = "pw-test-styles";
      style.innerHTML = `
        *,
        *::before,
        *::after {
          animation-delay: 0ms !important;
          animation-duration: 0ms !important;
          caret-color: transparent !important;
          scroll-behavior: auto !important;
          transition-delay: 0ms !important;
          transition-duration: 0ms !important;
        }
      `;
      (document.head ?? document.documentElement).appendChild(style);
    };

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", installTestStyles, { once: true });
    } else {
      installTestStyles();
    }

    const win = window as Window & {
      __scoutPerf?: { lcpMs: number | null };
    };
    win.__scoutPerf = { lcpMs: null };

    const observer = new PerformanceObserver((entryList) => {
      const entries = entryList.getEntries();
      const latest = entries.at(-1);
      if (latest && win.__scoutPerf) {
        win.__scoutPerf.lcpMs = latest.startTime;
      }
    });

    observer.observe({ type: "largest-contentful-paint", buffered: true });
    document.addEventListener(
      "visibilitychange",
      () => observer.disconnect(),
      { once: true },
    );
  });
}

export function trackNetworkFailures(page: Page): NetworkRecorder {
  const failures: string[] = [];

  const onResponse = (response: Awaited<ReturnType<Page["waitForResponse"]>>) => {
    const request = response.request();
    const resourceType = request.resourceType();
    const status = response.status();
    if (status < 400) return;
    if (!["document", "script", "stylesheet", "image", "fetch", "xhr"].includes(resourceType)) return;
    if (shouldIgnoreNetworkFailure(response.url(), resourceType, String(status))) return;
    failures.push(`${status} ${resourceType} ${response.url()}`);
  };

  const onRequestFailed = (request: Awaited<ReturnType<Page["waitForRequest"]>>) => {
    const failure = request.failure();
    if (shouldIgnoreNetworkFailure(request.url(), request.resourceType(), failure?.errorText)) return;
    failures.push(`${request.resourceType()} ${request.url()} ${failure?.errorText ?? "request failed"}`);
  };

  page.on("response", onResponse);
  page.on("requestfailed", onRequestFailed);

  return {
    failures,
    dispose: () => {
      page.off("response", onResponse);
      page.off("requestfailed", onRequestFailed);
    },
  };
}

export async function gotoAndWait(page: Page, routePath: string) {
  await preparePage(page);
  await page.goto(routePath, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle");
  await expect(page.locator("body")).toBeVisible();
}

export async function expectNoConsoleErrors(page: Page, fn: () => Promise<void>) {
  const errors: string[] = [];
  const onConsole = (msg: { type(): string; text(): string }) => {
    if (msg.type() === "error") errors.push(msg.text());
  };
  const onPageError = (err: Error) => errors.push(err.message);

  page.on("console", onConsole);
  page.on("pageerror", onPageError);
  await fn();
  page.off("console", onConsole);
  page.off("pageerror", onPageError);

  const realErrors = errors.filter(
    (error) =>
      !error.includes("favicon") &&
      !error.includes("Failed to load resource"),
  );
  expect(realErrors).toEqual([]);
}

export async function expectNoBrokenImages(page: Page) {
  const brokenImages = await page.evaluate(() =>
    Array.from(document.images)
      .filter((img) => img.complete && img.naturalWidth === 0)
      .map((img) => img.currentSrc || img.src || img.alt),
  );

  expect(brokenImages).toEqual([]);
}

export async function readVisibleHeading(page: Page) {
  const heading = page.getByRole("heading").first();
  await expect(heading).toBeVisible();
  return (await heading.textContent())?.trim() ?? "";
}

export async function collectPerformanceMetrics(page: Page) {
  return page.evaluate(() => {
    const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
    const resources = performance.getEntriesByType("resource") as PerformanceResourceTiming[];
    const lcp = (window as Window & { __scoutPerf?: { lcpMs: number | null } }).__scoutPerf?.lcpMs ?? null;

    return {
      domCompleteMs: nav ? nav.domComplete : null,
      lcpMs: lcp,
      totalBytes: resources.reduce((sum, resource) => sum + (resource.transferSize || 0), 0),
      resourceCount: resources.length,
      imageCount: resources.filter((resource) => resource.initiatorType === "img").length,
    };
  });
}
