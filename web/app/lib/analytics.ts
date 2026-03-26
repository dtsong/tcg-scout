import { track } from "@vercel/analytics";

/**
 * Custom event names tracked across the application.
 */
export type AnalyticsEvent =
  | "share_click"
  | "copy_link"
  | "deck_save"
  | "auth_signin";

/**
 * Track a custom analytics event. Wraps Vercel Analytics `track()` so the
 * rest of the codebase does not depend on the analytics vendor directly.
 *
 * In non-browser environments (SSR / tests) the call is a no-op.
 */
export function trackEvent(
  name: AnalyticsEvent,
  properties?: Record<string, string | number | boolean>,
): void {
  if (typeof window === "undefined") return;
  try {
    track(name, properties);
  } catch (err) {
    console.error("Analytics tracking failed:", err);
  }
}
