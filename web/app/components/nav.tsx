"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/app/lib/utils";
import { Crosshair } from "lucide-react";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/archetypes", label: "Archetypes" },
  { href: "/buylist", label: "Buy List" },
  { href: "/trends", label: "Trends" },
  { href: "/champions", label: "Champions League" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <nav className="border-b border-surface-600 bg-surface-800/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          <Link href="/" className="flex items-center gap-2 text-accent font-display font-bold text-lg">
            <Crosshair className="w-5 h-5" />
            Scout
          </Link>
          <div className="flex items-center gap-1 overflow-x-auto">
            {links.map(({ href, label }) => {
              const active =
                href === "/" ? pathname === "/" : pathname.startsWith(href);
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
