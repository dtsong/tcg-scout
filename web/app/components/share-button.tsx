"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Share2, Copy, Check, ExternalLink } from "lucide-react";
import { cn } from "@/app/lib/utils";
import { trackEvent } from "@/app/lib/analytics";

type PageType = "archetype" | "dashboard";

interface ShareButtonProps {
  title: string;
  text?: string;
  url?: string;
  pageType: PageType;
  className?: string;
}

export function ShareButton({
  title,
  text,
  url,
  pageType,
  className,
}: ShareButtonProps) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const resolvedUrl = typeof window !== "undefined" ? (url ?? window.location.href) : "";

  // Close on click outside
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  // Focus first menu item on open
  useEffect(() => {
    if (open && menuRef.current) {
      const first = menuRef.current.querySelector<HTMLElement>(
        '[role="menuitem"]',
      );
      requestAnimationFrame(() => first?.focus());
    }
  }, [open]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!open) {
        if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          setOpen(true);
        }
        return;
      }

      const items = menuRef.current
        ? Array.from(
            menuRef.current.querySelectorAll<HTMLElement>('[role="menuitem"]'),
          )
        : [];
      const current = document.activeElement as HTMLElement;
      const idx = items.indexOf(current);

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          items[(idx + 1) % items.length]?.focus();
          break;
        case "ArrowUp":
          e.preventDefault();
          items[(idx - 1 + items.length) % items.length]?.focus();
          break;
        case "Escape":
          e.preventDefault();
          setOpen(false);
          triggerRef.current?.focus();
          break;
        case "Tab":
          setOpen(false);
          break;
        case "Home":
          e.preventDefault();
          items[0]?.focus();
          break;
        case "End":
          e.preventDefault();
          items[items.length - 1]?.focus();
          break;
      }
    },
    [open],
  );

  const handlePrimary = async () => {
    // Try native Web Share API first (supported on mobile and some desktop browsers)
    if (typeof navigator !== "undefined" && navigator.share) {
      try {
        await navigator.share({
          title,
          text: text ?? title,
          url: resolvedUrl,
        });
        trackEvent("share_click", { method: "web-share", page_type: pageType });
        return;
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          return; // User cancelled -- do nothing
        }
        console.error("Web Share API failed:", err);
        // Fall through to dropdown as fallback
      }
    }
    setOpen((prev) => !prev);
  };

  const handleCopyLink = async () => {
    let success = false;
    try {
      await navigator.clipboard.writeText(resolvedUrl);
      success = true;
    } catch (clipErr) {
      console.warn("Clipboard API unavailable, trying fallback:", clipErr);
      try {
        const textarea = document.createElement("textarea");
        textarea.value = resolvedUrl;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        success = document.execCommand("copy");
        document.body.removeChild(textarea);
      } catch (fallbackErr) {
        console.error("Clipboard fallback failed:", fallbackErr);
      }
    }
    if (!success) {
      setOpen(false);
      return;
    }
    setCopied(true);
    trackEvent("share_click", { method: "copy-link", page_type: pageType });
    trackEvent("copy_link", { page_type: pageType });
    setTimeout(() => {
      setCopied(false);
      setOpen(false);
    }, 1500);
  };

  const handleTwitter = () => {
    const tweetText = encodeURIComponent(text ?? title);
    const tweetUrl = encodeURIComponent(resolvedUrl);
    window.open(
      `https://twitter.com/intent/tweet?text=${tweetText}&url=${tweetUrl}`,
      "_blank",
      "noopener,noreferrer",
    );
    trackEvent("share_click", { method: "twitter", page_type: pageType });
    setOpen(false);
  };

  return (
    <div ref={containerRef} className={cn("relative inline-block", className)}>
      <button
        ref={triggerRef}
        onClick={handlePrimary}
        onKeyDown={handleKeyDown}
        aria-haspopup="menu"
        aria-expanded={open}
        className={cn(
          "inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border transition-all",
          "bg-surface-700 border-surface-500 text-surface-300",
          "hover:text-slate-200 hover:border-surface-400",
        )}
      >
        <Share2 className="w-3.5 h-3.5" />
        Share
      </button>

      {open && (
        <div
          ref={menuRef}
          role="menu"
          aria-label="Share options"
          onKeyDown={handleKeyDown}
          className="absolute right-0 top-full mt-1.5 w-44 rounded-md border border-surface-600 bg-surface-700 shadow-lg shadow-black/40 z-50 overflow-hidden"
        >
          <button
            role="menuitem"
            tabIndex={-1}
            onClick={handleCopyLink}
            className={cn(
              "flex items-center gap-2 w-full px-3 py-2 text-xs text-left transition-colors",
              copied
                ? "text-emerald-400"
                : "text-surface-300 hover:bg-surface-600 hover:text-slate-200",
            )}
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5" />
                Copied!
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                Copy Link
              </>
            )}
          </button>
          <button
            role="menuitem"
            tabIndex={-1}
            onClick={handleTwitter}
            className="flex items-center gap-2 w-full px-3 py-2 text-xs text-left text-surface-300 hover:bg-surface-600 hover:text-slate-200 transition-colors"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            Share on X
          </button>
        </div>
      )}
    </div>
  );
}
