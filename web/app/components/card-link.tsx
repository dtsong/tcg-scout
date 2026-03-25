import Link from "next/link";
import { slugify } from "@/app/lib/utils";

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
      className={className ?? "hover:text-accent transition-colors"}
      onClick={(e) => e.stopPropagation()}
    >
      {name}
    </Link>
  );
}
