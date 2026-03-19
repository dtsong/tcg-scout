"use client";

import { useState, useRef, useEffect, type ReactNode } from "react";

export function Tooltip({
  content,
  children,
}: {
  content: ReactNode;
  children: ReactNode;
}) {
  const [visible, setVisible] = useState(false);
  const [position, setPosition] = useState<"top" | "bottom">("top");
  const triggerRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (visible && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setPosition(rect.top < 80 ? "bottom" : "top");
    }
  }, [visible]);

  return (
    <span
      ref={triggerRef}
      className="relative inline-flex"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      {children}
      {visible && (
        <span
          className={`absolute left-1/2 -translate-x-1/2 z-50 px-3 py-2 text-xs text-surface-200 bg-surface-700 border border-surface-500 rounded-lg shadow-lg max-w-[280px] w-max pointer-events-none ${
            position === "top" ? "bottom-full mb-2" : "top-full mt-2"
          }`}
        >
          {content}
          <span
            className={`absolute left-1/2 -translate-x-1/2 w-2 h-2 bg-surface-700 border-surface-500 rotate-45 ${
              position === "top"
                ? "top-full -mt-1 border-r border-b"
                : "bottom-full -mb-1 border-l border-t"
            }`}
          />
        </span>
      )}
    </span>
  );
}

export function InfoIcon({ tooltip }: { tooltip: ReactNode }) {
  return (
    <Tooltip content={tooltip}>
      <span className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full border border-surface-500 text-surface-400 text-[9px] leading-none cursor-help">
        i
      </span>
    </Tooltip>
  );
}
