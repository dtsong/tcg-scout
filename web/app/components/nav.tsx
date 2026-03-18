"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/app/lib/utils";
import { Crosshair } from "lucide-react";

export function Nav({ format }: { format: string }) {
  const pathname = usePathname();

  const links = [
    { href: `/${format}`, label: "Dashboard" },
    { href: `/${format}/archetypes`, label: "Archetypes" },
    { href: `/${format}/buylist`, label: "Buy List" },
    { href: `/${format}/trends`, label: "Trends" },
    { href: `/${format}/champions`, label: "Champions League" },
  ];

  return (
    <nav className="border-b border-surface-600 bg-surface-800/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2 text-accent font-display font-bold text-lg">
              <Crosshair className="w-5 h-5" />
              Scout
            </Link>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-surface-700 text-surface-300 border border-surface-600">
              {format}
            </span>
          </div>
          <div className="flex items-center gap-1 overflow-x-auto">
            {links.map(({ href, label }) => {
              const active =
                href === `/${format}`
                  ? pathname === `/${format}`
                  : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "px-3 py-1.5 text-sm rounded-md whitespace-nowrap transition-colors",
                    active
                      ? "bg-surface-600 text-slate-100"
                      : "text-surface-300 hover:text-slate-200 hover:bg-surface-700",
                  )}
                >
                  {label}
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </nav>
  );
}
