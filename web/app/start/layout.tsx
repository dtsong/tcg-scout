import Link from "next/link";
import { Crosshair } from "lucide-react";

export default function StartLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <nav className="border-b border-surface-600 bg-surface-800/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            <Link
              href="/"
              className="flex items-center gap-2 text-accent font-display font-bold text-lg"
            >
              <Crosshair className="w-5 h-5" />
              Scout
            </Link>
            <Link
              href="/"
              className="text-sm text-surface-300 hover:text-slate-200 transition-colors"
            >
              Back to app
            </Link>
          </div>
        </div>
      </nav>
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {children}
      </main>
      <footer className="border-t border-surface-700 mt-16">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <p className="text-xs text-surface-400">
            Data sourced from{" "}
            <a
              href="https://limitlesstcg.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:text-accent/80"
            >
              LimitlessTCG
            </a>{" "}
            and{" "}
            <a
              href="https://pokemon-card.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:text-accent/80"
            >
              pokemon-card.com
            </a>
          </p>
        </div>
      </footer>
    </>
  );
}
