"use client";

import { useState, useRef, useCallback, type ReactNode } from "react";
import { cn } from "@/app/lib/utils";

interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
}

export function Tooltip({ content, children }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const [position, setPosition] = useState<"top" | "bottom">("top");
  const triggerRef = useRef<HTMLSpanElement>(null);

  const show = useCallback(() => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setPosition(rect.top < 80 ? "bottom" : "top");
    }
    setVisible(true);
  }, []);

  const hide = useCallback(() => setVisible(false), []);

  return (
    <span
      ref={triggerRef}
      className="relative inline-flex"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {visible && (
        <span
          role="tooltip"
          className={cn(
            "absolute left-1/2 -translate-x-1/2 z-50 px-3 py-2 text-xs text-surface-200 bg-surface-700 border border-surface-500 rounded-lg shadow-lg max-w-[280px] w-max pointer-events-none",
            position === "top" ? "bottom-full mb-2" : "top-full mt-2",
          )}
        >
          {content}
          <span
            className={cn(
              "absolute left-1/2 -translate-x-1/2 w-2 h-2 bg-surface-700 border-surface-500 rotate-45",
              position === "top"
                ? "top-full -mt-1 border-r border-b"
                : "bottom-full -mb-1 border-l border-t",
            )}
          />
        </span>
      )}
    </span>
  );
}

interface InfoIconProps {
  tooltip: ReactNode;
}

export function InfoIcon({ tooltip }: InfoIconProps) {
  return (
    <Tooltip content={tooltip}>
      <span
        tabIndex={0}
        role="button"
        aria-label="More information"
        className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full border border-surface-500 text-surface-400 text-[9px] leading-none cursor-help"
      >
        i
      </span>
    </Tooltip>
  );
}
