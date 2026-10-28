"use client";

import { motion } from "motion/react";

import { InfoTip } from "@/components/ui/primitives";
import { clusterColor } from "@/lib/palette";
import { cn, pct } from "@/lib/utils";
import type { Hit, MatchMethod } from "@/types/api";

export function bandColor(label: string, method: MatchMethod) {
  const i = method.bands.findIndex((b) => b.label === label);
  return ["#48E1CD", "#4CA8D8", "#E8B56B"][i] ?? "#9BB3C6";
}

function Bar({ value, color, label }: { value: number; color: string; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-14 shrink-0 font-mono text-[10px] uppercase tracking-wide text-muted">{label}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-line/60">
        <motion.div
          className="h-full rounded-full"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: `${Math.min(100, value * 100)}%` }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        />
      </div>
      <span className="tabular w-12 text-right font-mono text-xs text-ink">{pct(value)}</span>
    </div>
  );
}

export function HitList({
  hits,
  method,
  selected,
  onSelect,
}: {
  hits: Hit[];
  method: MatchMethod;
  selected: number;
  onSelect: (rank: number) => void;
}) {
  return (
    <div className="flex flex-col gap-2" role="listbox" aria-label="Closest matching reference proteins">
      {hits.map((h, i) => {
        const active = h.rank === selected;
        const bc = bandColor(h.interpretation, method);
        return (
          <motion.button
            key={h.protein_id}
            role="option"
            aria-selected={active}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.05 }}
            onClick={() => onSelect(h.rank)}
            className={cn(
              "group relative w-full rounded-xl border p-3.5 text-left transition",
              active ? "border-teal/50 bg-elevated glow-ring" : "border-line/70 bg-void/40 hover:border-line hover:bg-elevated/50",
            )}
          >
            <div className="flex items-center gap-3">
              <span className={cn("grid size-7 shrink-0 place-items-center rounded-md font-mono text-xs", active ? "bg-teal text-void" : "bg-line/60 text-muted")}>
                {h.rank}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate font-mono text-sm font-semibold">{h.protein_name}</span>
                  <span className="font-mono text-[10px]" style={{ color: clusterColor(h.reference.subcluster) }}>
                    {h.reference.subcluster}
                  </span>
                </div>
                <div className="truncate text-[11px]" style={{ color: bc }}>
                  {h.interpretation}
                </div>
              </div>
              <div className="text-right">
                <div className="tabular font-mono text-lg font-semibold" style={{ color: bc }}>
                  {pct(h.identity, 0)}
                </div>
                <div className="font-mono text-[9px] uppercase tracking-wider text-muted">identity</div>
              </div>
            </div>
            <div className="mt-3 flex flex-col gap-1.5">
              <Bar label="Query" value={h.query_coverage} color="#4CA8D8" />
              <Bar label="Ref" value={h.target_coverage} color="#69E8C3" />
            </div>
            <div className="mt-2.5 flex flex-wrap gap-x-3 gap-y-1 font-mono text-[10px] text-muted">
              <span>
                norm <span className="text-ink">{h.normalised_score.toFixed(3)}</span>
              </span>
              <span>
                raw <span className="text-ink">{h.raw_score.toFixed(0)}</span>
              </span>
              <span>
                z <span className="text-ink">{h.shuffled_z.toFixed(1)}</span>
              </span>
              <span>
                cols <span className="text-ink">{h.aligned_columns}</span>
              </span>
            </div>
          </motion.button>
        );
      })}
    </div>
  );
}

export function MatchComparison({ hits, method }: { hits: Hit[]; method: MatchMethod }) {
  const metrics = [
    { key: "identity", label: "Identity", color: "#48E1CD", tip: method.identity_definition },
    { key: "query_coverage", label: "Query coverage", color: "#4CA8D8", tip: "Share of your sequence inside the aligned region." },
    { key: "target_coverage", label: "Reference coverage", color: "#69E8C3", tip: "Share of the reference protein inside the aligned region." },
    { key: "normalised_score", label: "Normalised score", color: "#B49CF5", tip: method.ranking },
  ] as const;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] border-separate border-spacing-y-1.5 text-sm">
        <thead>
          <tr className="text-left">
            <th className="eyebrow pb-1 font-normal">Rank · protein</th>
            {metrics.map((m) => (
              <th key={m.key} className="eyebrow pb-1 font-normal">
                <span className="inline-flex items-center gap-1">
                  {m.label} <InfoTip content={m.tip} />
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {hits.map((h) => (
            <tr key={h.protein_id}>
              <td className="pr-3 font-mono text-xs">
                <span className="text-muted">{h.rank}.</span> {h.protein_name}
              </td>
              {metrics.map((m) => {
                const v = h[m.key];
                return (
                  <td key={m.key} className="pr-3">
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-full max-w-[140px] overflow-hidden rounded-full bg-line/50">
                        <div className="h-full rounded-full" style={{ width: `${Math.min(1, v) * 100}%`, background: m.color }} />
                      </div>
                      <span className="tabular w-11 font-mono text-xs">{m.key === "normalised_score" ? v.toFixed(2) : pct(v, 0)}</span>
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
