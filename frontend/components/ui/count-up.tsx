"use client";

import { animate } from "motion/react";
import { useEffect, useRef, useState } from "react";

// Ids that have already counted up this session: revisiting a page or a rerender shows the final value straight away.
const played = new Set<string>();

/**
 * Counts an integer statistic up from zero the first time it is shown.
 * Only use it for real values read from the analysis outputs, never for placeholders.
 * The final value reserves the width (no layout shift) and is what screen readers hear.
 */
export function CountUp({
  id,
  value,
  format = (n) => n.toLocaleString("en-GB"),
  duration = 0.9,
}: {
  id: string;
  value: number;
  format?: (n: number) => string;
  duration?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const fmt = useRef(format);
  fmt.current = format;
  const [start] = useState(() => (played.has(id) ? value : 0));

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const show = (n: number) => (el.textContent = fmt.current(n));
    if (played.has(id) || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      played.add(id);
      show(value);
      return;
    }
    const controls = animate(0, value, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => show(Math.round(v)),
      onComplete: () => played.add(id),
    });
    return () => controls.stop();
  }, [id, value, duration]);

  const final = format(value);
  return (
    <span className="inline-grid">
      <span className="invisible col-start-1 row-start-1" aria-hidden>
        {final}
      </span>
      <span ref={ref} className="col-start-1 row-start-1" aria-hidden>
        {format(start)}
      </span>
      <span className="sr-only">{final}</span>
    </span>
  );
}
