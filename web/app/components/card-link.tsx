"use client";

import Link from "next/link";
import { slugify, cn } from "@/app/lib/utils";

// Links a card name to its detail page at /{format}/cards/{slug}.
// Assumes the target page exists (card is in the card index export).
// If the card is missing, the link resolves to a 404.
// stopPropagation prevents parent clickable containers (e.g., expandable
// table rows) from toggling on link click. Harmless in non-clickable contexts.
// hover:text-accent is applied last via cn() so it cannot be overridden by
// the className prop -- this is intentional.
export function CardLink({
  name,
  format,
  className,
}: {
  name: string;
  format: string;
  className?: string;
}) {
  const slug = slugify(name);
  if (!slug || !format) {
    return <span className={className}>{name}</span>;
  }
  return (
    <Link
      href={`/${format}/cards/${slug}`}
      className={cn(className, "hover:text-accent transition-colors")}
      onClick={(e) => e.stopPropagation()}
    >
      {name}
    </Link>
  );
}
