"use client";

import { useEffect, useRef, useState } from "react";

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

const DURATION = 600; // ms

/**
 * Animates a number from 0 to `target` over 600ms with ease-out.
 * Respects prefers-reduced-motion by returning the target immediately.
 * @param decimals - number of decimal places to round to (default: 0)
 * Use with `font-mono tabular-nums` to prevent digit width shifts.
 */
export function useCountUp(target: number, decimals = 0): number {
  const [value, setValue] = useState(target);
  const rafRef = useRef<number | null>(null);
  const startRef = useRef<number | null>(null);

  useEffect(() => {
    const prefersReduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    if (prefersReduced || target === 0) {
      setValue(target);
      return;
    }

    // Reset to 0 then animate up
    setValue(0);
    startRef.current = null;

    const animate = (timestamp: number) => {
      if (startRef.current === null) startRef.current = timestamp;
      const elapsed = timestamp - startRef.current;
      const progress = Math.min(elapsed / DURATION, 1);
      const eased = easeOutCubic(progress);

      const factor = Math.pow(10, decimals);
      setValue(Math.round(eased * target * factor) / factor);

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      } else {
        setValue(target);
      }
    };

    rafRef.current = requestAnimationFrame(animate);

    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [target, decimals]);

  return value;
}
