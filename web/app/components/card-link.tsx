"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { slugify, cn } from "@/app/lib/utils";

// Links a card name to its detail page at /{format}/cards/{slug}.
// Assumes the target page exists (card is in the card index export).
// If the card is missing, the link resolves to a 404 (dynamicParams=false).
// stopPropagation prevents parent clickable containers (e.g., expandable
// table rows) from toggling on link click. Harmless in non-clickable contexts.
// hover:text-accent is applied last via cn() so twMerge will discard any
// hover:text-* class from className -- this is intentional.
export function CardLink({
  name,
  className,
}: {
  name: string;
  className?: string;
}) {
  const { format } = useParams<{ format: string }>();
  const slug = slugify(name);
  if (!slug || !format) {
    console.warn(`[CardLink] fallback to span: name="${name}", format="${format}"`);
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
