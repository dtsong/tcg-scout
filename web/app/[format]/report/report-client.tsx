"use client";

import Link from "next/link";
import type { MetaReport, ReportSection } from "@/app/lib/types";

function parseInlineLinks(text: string, format: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = linkRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const [, label, href] = match;
    const isExternal = href.startsWith("http");
    if (isExternal) {
      parts.push(
        <a
          key={match.index}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent hover:text-accent/80 underline underline-offset-2"
        >
          {label}
        </a>
      );
    } else {
      const resolvedHref = `/${format}${href}`;
      parts.push(
        <Link
          key={match.index}
          href={resolvedHref}
          className="text-accent hover:text-accent/80 underline underline-offset-2"
        >
          {label}
        </Link>
      );
    }
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts;
}

function SectionCard({ section, format }: { section: ReportSection; format: string }) {
  const paragraphs = section.content.split(/\n\n+/).filter(Boolean);

  return (
    <div className="bg-surface-800 rounded-xl border border-surface-600 p-6 space-y-4">
      <h2 className="font-display text-lg font-semibold text-amber-400">
        {section.title}
      </h2>
      <div className="space-y-3">
        {paragraphs.map((para, i) => (
          <p key={i} className="text-slate-300 leading-relaxed font-body text-sm">
            {parseInlineLinks(para, format)}
          </p>
        ))}
      </div>
      {section.highlights && section.highlights.length > 0 && (
        <ul className="mt-3 space-y-1.5 border-t border-surface-600 pt-4">
          {section.highlights.map((h, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-slate-400">
              <span className="mt-1 w-1.5 h-1.5 rounded-full bg-amber-500/60 flex-shrink-0" />
              <span>{parseInlineLinks(h, format)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ReportClient({ report, format }: { report: MetaReport; format: string }) {
  const generatedDate = new Date(report.generated_at).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-2xl font-bold text-slate-100">
          Meta Report
        </h1>
        <p className="text-sm text-surface-300 mt-1">
          Generated {generatedDate}{" "}
          <Link href="/guide#report" className="text-accent hover:text-accent/80 transition-colors">
            How this works &rarr;
          </Link>
        </p>
      </div>

      <div className="space-y-4">
        {report.sections.map((section) => (
          <SectionCard key={section.id} section={section} format={format} />
        ))}
      </div>

      {report.sections.length === 0 && (
        <p className="text-surface-300 text-sm">This report has no sections yet.</p>
      )}
    </div>
  );
}
