"use client";

import { Layers } from "lucide-react";

import { C, tint } from "@/lib/palette";
import { cn } from "@/lib/utils";
import type { BatchResult } from "@/types/api";

import { ASSESSMENT, categoryOf, CATEGORY_ORDER, type UiCategory } from "../assessment";

/** Counts per evidence category. Clicking a tile filters the results table. */
export function AssessmentSummary({
  results,
  total,
  filter,
  onFilter,
}: {
  results: BatchResult[];
  total: number;
  filter: string;
  onFilter: (f: string) => void;
}) {
  const counts = Object.fromEntries(CATEGORY_ORDER.map((c) => [c, 0])) as Record<UiCategory, number>;
  for (const r of results) {
    const c = categoryOf(r);
    if (c) counts[c] += 1;
  }
  const labels: Record<UiCategory, string> = {
    green: "Green · likely",
    yellow: "Yellow · possible",
    red: "Red · unlikely",
    insufficient: "Insufficient evidence",
    invalid: "Invalid sequences",
  };

  const tiles: { key: string; label: string; value: number; color: string; Icon: typeof Layers; hint?: string }[] = [
    { key: "all", label: "Proteins analysed", value: results.length, color: C.cyan, Icon: Layers, hint: results.length < total ? `of ${total} records` : "records" },
    ...CATEGORY_ORDER.map((c) => ({ key: c, label: labels[c], value: counts[c], color: ASSESSMENT[c].color, Icon: ASSESSMENT[c].icon })),
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6" role="group" aria-label="Evidence assessment summary">
      {tiles.map(({ key, label, value, color, Icon, hint }) => {
        const active = filter === key;
        return (
          <button
            key={key}
            type="button"
            onClick={() => onFilter(active && key !== "all" ? "all" : key)}
            aria-pressed={active}
            className={cn(
              "panel flex flex-col items-start gap-1 p-4 text-left transition duration-200 hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/60 motion-reduce:transform-none",
            )}
            style={active ? { borderColor: tint(color, 60), boxShadow: `0 0 0 1px ${tint(color, 45)}` } : undefined}
          >
            <span className="flex items-center gap-1.5 text-xs text-muted">
              <Icon className="size-3.5" style={{ color }} aria-hidden /> {label}
            </span>
            <span className="tabular font-mono text-2xl font-semibold" style={{ color }}>
              {value}
            </span>
            {hint && <span className="text-[11px] text-muted">{hint}</span>}
          </button>
        );
      })}
    </div>
  );
}
