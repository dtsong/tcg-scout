"use client";

import { useEffect } from "react";
import { Crosshair } from "lucide-react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[error-boundary]", error);
  }, [error]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4">
      <Crosshair className="w-10 h-10 text-surface-500 mb-6" />
      <h1 className="font-display text-3xl font-bold text-slate-100 mb-2">
        Something went wrong
      </h1>
      <p className="text-sm text-surface-300 mb-8 text-center max-w-md">
        An unexpected error occurred. Try refreshing, or head back to the homepage.
      </p>
      {error.digest && (
        <p className="text-xs text-surface-500 mb-4 font-mono">
          Reference: {error.digest}
        </p>
      )}
      <div className="flex items-center gap-3">
        <button
          onClick={reset}
          className="px-5 py-2.5 border border-surface-600 text-surface-300 font-display font-medium text-sm rounded-lg hover:border-surface-500 hover:text-slate-200 transition-colors"
        >
          Try again
        </button>
        <a
          href="/"
          className="px-5 py-2.5 bg-accent text-surface-900 font-display font-semibold text-sm rounded-lg hover:bg-accent/90 transition-colors"
        >
          Back to Scout
        </a>
      </div>
    </div>
  );
}
