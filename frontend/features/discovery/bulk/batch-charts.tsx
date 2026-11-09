"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Panel, PanelHeader } from "@/components/ui/primitives";
import { axisProps, ChartTooltip, gridProps } from "@/components/viz/chart-kit";
import { C } from "@/lib/palette";
import type { BatchResult } from "@/types/api";

import { EVIDENCE_STATUS } from "../evidence";

type Datum = { label: string; n: number; color: string };

function MiniBars({ title, note, data, xLabel }: { title: string; note: string; data: Datum[]; xLabel?: string }) {
  return (
    <div className="rounded-xl border border-line/70 bg-void/40 p-4">
      <div className="text-[13px] font-medium">{title}</div>
      <p className="mt-0.5 text-[11px] text-muted">{note}</p>
      <div className="mt-3 h-[170px]">
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 4, right: 6, bottom: xLabel ? 14 : 0, left: -22 }}>
            <CartesianGrid {...gridProps} vertical={false} />
            <XAxis
              dataKey="label"
              {...axisProps}
              interval={0}
              tick={{ ...axisProps.tick, fontSize: 10 }}
              label={xLabel ? { value: xLabel, position: "bottom", offset: 0, fill: "var(--color-muted)", fontSize: 10 } : undefined}
            />
            <YAxis allowDecimals={false} {...axisProps} />
            <Tooltip
              cursor={{ fill: "color-mix(in srgb, var(--color-electric) 8%, transparent)" }}
              content={({ payload }) => {
                const d = payload?.[0]?.payload as Datum | undefined;
                return d ? <ChartTooltip title={d.label} rows={[{ label: "Proteins", value: d.n, color: d.color }]} /> : null;
              }}
            />
            <Bar dataKey="n" radius={[3, 3, 0, 0]} isAnimationActive={false}>
              {data.map((d) => (
                <Cell key={d.label} fill={d.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function histogram(values: number[], edges: number[], fmt: (lo: number, hi: number) => string, color: string): Datum[] {
  return edges.slice(0, -1).map((lo, i) => {
    const hi = edges[i + 1];
    const last = i === edges.length - 2;
    return { label: fmt(lo, hi), n: values.filter((v) => v >= lo && (last ? v <= hi : v < hi)).length, color };
  });
}

/** Descriptive summaries of the batch. No chart shows a predicted activity, because none exists. */
export function BatchCharts({ results }: { results: BatchResult[] }) {
  const analysed = results.filter((r) => r.status === "analysed" || r.status === "duplicate");
  const status: Datum[] = [
    { label: "Analysed", n: results.filter((r) => r.status === "analysed").length, color: C.mint },
    { label: "Duplicate", n: results.filter((r) => r.status === "duplicate").length, color: C.amber },
    { label: "Invalid", n: results.filter((r) => r.status === "invalid").length, color: C.rose },
    { label: "Error", n: results.filter((r) => r.status === "error").length, color: C.violet },
  ];
  const evidence: Datum[] = (["experimental", "similarity", "unknown"] as const).map((k) => ({
    label: EVIDENCE_STATUS[k].label.replace(" (identical reference)", ""),
    n: analysed.filter((r) => r.evidence_status === k).length,
    color: EVIDENCE_STATUS[k].color,
  }));
  const identity = histogram(
    analysed.map((r) => 100 * (r.hits?.[0]?.identity ?? 0)),
    [0, 25, 40, 60, 80, 90, 100],
    (lo, hi) => `${lo}–${hi}`,
    C.sky,
  );
  const lengths = analysed.map((r) => r.length ?? 0);
  const maxLen = Math.max(400, ...lengths);
  const step = Math.ceil(maxLen / 6 / 50) * 50;
  const lengthBins = histogram(lengths, Array.from({ length: 7 }, (_, i) => i * step), (lo, hi) => `${lo}–${hi}`, C.violet);

  return (
    <Panel>
      <PanelHeader eyebrow="Batch summary" title="What this batch contains" description="Counts over the analysed records. These describe the input; they are not predictions." />
      <div className="stagger grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-4">
        <MiniBars title="Analysis status" note="Every record, including rejected ones." data={status} />
        <MiniBars title="Evidence category" note="Kind of evidence the nearest characterised protein provides." data={evidence} />
        <MiniBars title="Identity to nearest characterised protein" note="Below 25% there is no reliable homology; 25–40% is the twilight zone." data={identity} xLabel="% identity" />
        <MiniBars title="Sequence length" note="Lengths of the analysed sequences." data={lengthBins} xLabel="amino acids" />
      </div>
    </Panel>
  );
}
