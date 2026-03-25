"use client";

import Link from "next/link";
import { slugify } from "@/app/lib/utils";
import { cn } from "@/app/lib/utils";

// Links a card name to its detail page at /{format}/cards/{slug}.
// Assumes the target page exists (card is in the card index export).
// stopPropagation prevents parent clickable containers (e.g., expandable
// table rows in ResultsTable/Top4CardStats) from toggling on link click.
export function CardLink({
  name,
  format,
  className,
}: {
  name: string;
  format: string;
  className?: string;
}) {
  return (
    <Link
      href={`/${format}/cards/${slugify(name)}`}
      className={cn("hover:text-accent transition-colors", className)}
      onClick={(e) => e.stopPropagation()}
    >
      {name}
    </Link>
  );
}
