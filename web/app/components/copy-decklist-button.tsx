"use client";

import { useState } from "react";
import { Copy, Check } from "lucide-react";
import { cn } from "@/app/lib/utils";

interface CopyableCard {
  card_name: string;
  count: number;
  category?: "Pokemon" | "Trainer" | "Energy" | string;
  set_code?: string | null;
  set_number?: string | null;
}

function formatDecklist(cards: CopyableCard[]): string {
  const pokemon: CopyableCard[] = [];
  const trainer: CopyableCard[] = [];
  const energy: CopyableCard[] = [];

  for (const card of cards) {
    switch (card.category) {
      case "Pokemon":
        pokemon.push(card);
        break;
      case "Energy":
        energy.push(card);
        break;
      case "Trainer":
        trainer.push(card);
        break;
      default:
        trainer.push(card);
    }
  }

  const formatLine = (card: CopyableCard): string => {
    const parts = [String(card.count), card.card_name];
    if (card.set_code) parts.push(card.set_code);
    if (card.set_number) parts.push(card.set_number);
    return parts.join(" ");
  };

  const sections: string[] = [];

  if (pokemon.length > 0) {
    const total = pokemon.reduce((sum, c) => sum + c.count, 0);
    sections.push(
      `Pok\u00e9mon: ${total}`,
      ...pokemon.map(formatLine),
    );
  }

  if (trainer.length > 0) {
    const total = trainer.reduce((sum, c) => sum + c.count, 0);
    if (sections.length > 0) sections.push("");
    sections.push(
      `Trainer: ${total}`,
      ...trainer.map(formatLine),
    );
  }

  if (energy.length > 0) {
    const total = energy.reduce((sum, c) => sum + c.count, 0);
    if (sections.length > 0) sections.push("");
    sections.push(
      `Energy: ${total}`,
      ...energy.map(formatLine),
    );
  }

  return sections.join("\n");
}

export function CopyDecklistButton({
  cards,
  className,
  compact = false,
}: {
  cards: CopyableCard[];
  className?: string;
  compact?: boolean;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    const text = formatDecklist(cards);
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className={cn(
        "inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border transition-all",
        copied
          ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
          : "bg-surface-700 border-surface-500 text-surface-300 hover:text-slate-200 hover:border-surface-400",
        className,
      )}
    >
      {copied ? (
        <>
          <Check className="w-3.5 h-3.5" />
          {!compact && "Copied!"}
        </>
      ) : (
        <>
          <Copy className="w-3.5 h-3.5" />
          {!compact && "Copy Decklist"}
        </>
      )}
    </button>
  );
}
