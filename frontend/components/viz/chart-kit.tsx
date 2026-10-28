"use client";

import { CHART } from "@/lib/palette";

// Shared Recharts styling so every chart reads as one system.
export const axisProps = {
  stroke: CHART.grid,
  tick: { fill: CHART.axis, fontSize: 11, fontFamily: "var(--font-geist-mono)" },
  tickLine: false,
  axisLine: { stroke: CHART.grid },
} as const;

export const gridProps = { stroke: CHART.grid, strokeOpacity: 0.45, strokeDasharray: "2 4" } as const;

export function ChartTooltip({
  title,
  rows,
}: {
  title?: React.ReactNode;
  rows: { label: React.ReactNode; value: React.ReactNode; color?: string }[];
}) {
  return (
    <div className="min-w-40 rounded-lg border border-line bg-[#0b1726]/95 px-3 py-2 text-xs shadow-2xl backdrop-blur">
      {title && <div className="mb-1.5 font-medium text-ink">{title}</div>}
      {rows.map((r, i) => (
        <div key={i} className="flex items-center justify-between gap-4 py-0.5">
          <span className="flex items-center gap-1.5 text-muted">
            {r.color && <span className="size-2 rounded-full" style={{ background: r.color }} />}
            {r.label}
          </span>
          <span className="tabular font-mono text-ink">{r.value}</span>
        </div>
      ))}
    </div>
  );
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1.5">
      {items.map((i) => (
        <span key={i.label} className="flex items-center gap-1.5 text-xs text-muted">
          <span className="size-2.5 rounded-sm" style={{ background: i.color }} />
          {i.label}
        </span>
      ))}
    </div>
  );
}
