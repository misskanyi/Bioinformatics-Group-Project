"use client";

import { Lightbulb, RotateCcw } from "lucide-react";
import { useInView, useReducedMotion } from "motion/react";
import { useRef, useState } from "react";

import { CHART } from "@/lib/palette";
import { cn } from "@/lib/utils";

// Shared Recharts styling so every chart reads as one system.
// Colours are CSS variables, so axes, grid and labels follow the theme.
export const axisProps = {
  stroke: CHART.grid,
  tick: { fill: CHART.axis, fontSize: 11, fontFamily: "var(--font-geist-mono)" },
  tickLine: false,
  axisLine: { stroke: CHART.grid },
} as const;

export const gridProps = { stroke: CHART.grid, strokeOpacity: 0.45, strokeDasharray: "2 4" } as const;

/** Axis title props (Recharts `label`). */
export const axisLabel = (value: string, position: "bottom" | "insideLeft" = "bottom") =>
  position === "bottom"
    ? { value, position, fill: CHART.axis, fontSize: 11, offset: 0 }
    : { value, angle: -90, position, fill: CHART.axis, fontSize: 11, style: { textAnchor: "middle" } };

/** Hover band behind the active category. */
export const barCursor = { fill: CHART.cursor } as const;

/**
 * Recharts animation props: bars grow from the baseline (lines draw) the
 * first time, and morph to new values when `data` changes, e.g. after a
 * filter. Between those, animation is switched off, so hover rerenders never
 * replay it. Static under prefers-reduced-motion.
 */
export function useChartMotion(data: unknown, duration = 650) {
  const reduce = useReducedMotion();
  const [settled, setSettled] = useState<unknown>(undefined);
  return {
    isAnimationActive: !reduce && settled !== data,
    animationDuration: duration,
    animationEasing: "ease-out" as const,
    onAnimationEnd: () => setSettled(data),
  };
}

/**
 * Mounts the chart only once it scrolls into view, so its entrance animation
 * is actually seen. The placeholder keeps the final height: no layout shift.
 */
export function ChartInView({ className, children }: { className: string; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const seen = useInView(ref, { once: true, margin: "0px 0px -60px 0px" });
  return (
    <div ref={ref} className={className}>
      {seen ? children : null}
    </div>
  );
}

export function ChartTooltip({
  title,
  rows,
  note,
}: {
  title?: React.ReactNode;
  rows: { label: React.ReactNode; value: React.ReactNode; color?: string }[];
  note?: React.ReactNode;
}) {
  return (
    <div className="popover min-w-40 max-w-72 rounded-lg px-3 py-2 text-xs">
      {title && <div className="mb-1.5 font-medium text-ink">{title}</div>}
      {rows.map((r, i) => (
        <div key={i} className="flex items-center justify-between gap-4 py-0.5">
          <span className="flex items-center gap-1.5 text-muted">
            {r.color && <span className="size-2 shrink-0 rounded-full" style={{ background: r.color }} />}
            {r.label}
          </span>
          <span className="tabular font-mono text-ink">{r.value}</span>
        </div>
      ))}
      {note && <div className="mt-1.5 border-t border-line/70 pt-1.5 text-[11px] leading-snug text-muted">{note}</div>}
    </div>
  );
}

type LegendItem = { label: string; color: string; key?: string };

/**
 * Chart legend. Static by default; pass `onToggle` to make each entry a
 * button that hides / shows its series, and `onHover` to emphasise it.
 */
export function Legend({
  items,
  hidden,
  onToggle,
  onHover,
  className,
}: {
  items: LegendItem[];
  hidden?: Set<string>;
  onToggle?: (key: string) => void;
  onHover?: (key: string | null) => void;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap gap-x-4 gap-y-1.5", className)}>
      {items.map((i) => {
        const key = i.key ?? i.label;
        const off = hidden?.has(key);
        const swatch = <span className="size-2.5 shrink-0 rounded-sm transition-opacity duration-200" style={{ background: i.color, opacity: off ? 0.25 : 1 }} />;
        return onToggle ? (
          <button
            key={key}
            type="button"
            aria-pressed={!off}
            onClick={() => onToggle(key)}
            onMouseEnter={() => onHover?.(key)}
            onMouseLeave={() => onHover?.(null)}
            onFocus={() => onHover?.(key)}
            onBlur={() => onHover?.(null)}
            className={cn(
              "flex items-center gap-1.5 rounded px-1 py-0.5 text-xs transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/50",
              off ? "text-muted/60 line-through" : "text-muted hover:text-ink",
            )}
          >
            {swatch}
            {i.label}
          </button>
        ) : (
          <span key={key} className="flex items-center gap-1.5 text-xs text-muted">
            {swatch}
            {i.label}
          </span>
        );
      })}
    </div>
  );
}

/** Accessible segmented control (radio group) for chart options. */
export function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted">{label}</span>
      <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg border border-line bg-surface/80 p-0.5">
        {options.map((o) => {
          const on = o.value === value;
          return (
            <button
              key={o.value}
              type="button"
              role="radio"
              aria-checked={on}
              onClick={() => onChange(o.value)}
              className={cn(
                "rounded-md px-2.5 py-1 text-xs font-medium transition duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/50",
                on ? "bg-electric/15 text-cyan shadow-[inset_0_0_0_1px_var(--glow-ring)]" : "text-muted hover:text-ink",
              )}
            >
              {o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Row of chart controls with an optional reset button (shown only when something differs from the default). */
export function ChartControls({ children, onReset, dirty }: { children: React.ReactNode; onReset?: () => void; dirty?: boolean }) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-x-5 gap-y-2.5">
      {children}
      {onReset && (
        <button
          type="button"
          onClick={onReset}
          disabled={!dirty}
          className="ml-auto inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted transition hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/50 disabled:pointer-events-none disabled:opacity-40"
        >
          <RotateCcw className="size-3.5" /> Reset
        </button>
      )}
    </div>
  );
}

/** Short interpretation under a chart. Only state what the plotted data shows. */
export function Takeaway({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("mt-3 flex gap-2.5 rounded-lg border border-teal/25 bg-teal/[0.05] px-3.5 py-2.5 text-[13px] leading-relaxed", className)}>
      <Lightbulb className="mt-0.5 size-4 shrink-0 text-teal" aria-hidden />
      <div className="text-ink/85">
        <span className="font-medium text-teal">Key takeaway · </span>
        {children}
      </div>
    </div>
  );
}
