"use client";

import { useEffect, useRef, useState } from "react";

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

const DURATION = 600; // ms

/**
 * Animates a number from 0 to `target` over 600ms with ease-out.
 * Respects prefers-reduced-motion by returning the target immediately.
 * Use with `font-mono tabular-nums` to prevent digit width shifts.
 */
export function useCountUp(target: number, decimals = 0): number {
  const [value, setValue] = useState(0);
  const rafRef = useRef<number | null>(null);
  const startRef = useRef<number | null>(null);
  const reducedMotion = useRef(false);

  useEffect(() => {
    reducedMotion.current = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
  }, []);

  useEffect(() => {
    if (reducedMotion.current || target === 0) {
      setValue(target);
      return;
    }

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
