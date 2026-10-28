"use client";

import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Select, Tabs, TabsList, TabsTrigger } from "@/components/ui/primitives";
import { axisProps, ChartTooltip, gridProps, Legend } from "@/components/viz/chart-kit";
import { clusterColor, OUTCOME_COLORS, OUTCOME_LABELS } from "@/lib/palette";
import { sortGroups } from "@/lib/utils";
import type { Assay, AssayOutcome, TemperatureSeries } from "@/types/api";

const OUTCOMES: AssayOutcome[] = ["detected", "not detected", "unclear", "excluded"];

/** Histogram of reported assay temperatures, stacked by outcome. */
export function TemperatureHistogram({ assays }: { assays: Assay[] }) {
  const [unit, setUnit] = useState<"assays" | "proteins">("proteins");
  const rows = useMemo(() => {
    const bins = new Map<number, Record<string, Set<number> | number>>();
    for (const a of assays) {
      if (a.temperature_c == null) continue;
      const b = Math.floor(a.temperature_c / 5) * 5;
      const row = bins.get(b) ?? Object.fromEntries(OUTCOMES.map((o) => [o, unit === "assays" ? 0 : new Set<number>()]));
      if (unit === "assays") (row[a.degradation_detected] as number)++;
      else (row[a.degradation_detected] as Set<number>).add(a.protein_id);
      bins.set(b, row);
    }
    return [...bins.entries()]
      .sort((x, y) => x[0] - y[0])
      .map(([b, r]) => ({
        bin: `${b}–${b + 4}`,
        ...Object.fromEntries(OUTCOMES.map((o) => [o, typeof r[o] === "number" ? r[o] : (r[o] as Set<number>).size])),
      }));
  }, [assays, unit]);
  const missing = assays.filter((a) => a.temperature_c == null).length;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <Tabs value={unit} onValueChange={(v) => setUnit(v as typeof unit)}>
          <TabsList>
            <TabsTrigger value="proteins">Distinct proteins</TabsTrigger>
            <TabsTrigger value="assays">Assay records</TabsTrigger>
          </TabsList>
        </Tabs>
        <span className="text-xs text-muted">
          {unit === "proteins"
            ? "Each protein counted once per bin and outcome, so repeated measurements do not inflate bars."
            : "Every reported assay; heavily studied proteins contribute many bars."}
        </span>
      </div>
      <div className="h-[300px]">
        <ResponsiveContainer>
          <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 22, left: -8 }}>
            <CartesianGrid {...gridProps} vertical={false} />
            <XAxis dataKey="bin" {...axisProps} label={{ value: "Assay temperature (°C, 5 °C bins)", position: "bottom", fill: "#9BB3C6", fontSize: 11 }} />
            <YAxis {...axisProps} allowDecimals={false} />
            <Tooltip
              cursor={{ fill: "rgb(72 225 205 / 0.06)" }}
              content={({ payload, label }) =>
                payload?.length ? (
                  <ChartTooltip
                    title={`${label} °C`}
                    rows={OUTCOMES.map((o) => ({
                      label: OUTCOME_LABELS[o],
                      value: (payload[0].payload as Record<string, number>)[o],
                      color: OUTCOME_COLORS[o],
                    }))}
                  />
                ) : null
              }
            />
            {OUTCOMES.map((o, i) => (
              <Bar key={o} dataKey={o} stackId="t" fill={OUTCOME_COLORS[o]} radius={i === OUTCOMES.length - 1 ? [3, 3, 0, 0] : 0} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <Legend items={OUTCOMES.map((o) => ({ label: OUTCOME_LABELS[o], color: OUTCOME_COLORS[o] }))} />
      {missing > 0 && <p className="mt-2 text-xs text-muted">{missing} assay records report no temperature and are not shown.</p>}
    </div>
  );
}

/** Temperatures with detected activity per subgroup: one dot per protein × temperature. */
export function ClusterTemperatureStrip({ assays }: { assays: Assay[] }) {
  const data = useMemo(() => {
    const seen = new Set<string>();
    const by: Record<string, { t: number; name: string }[]> = {};
    for (const a of assays) {
      if (a.degradation_detected !== "detected" || a.temperature_c == null) continue;
      const k = `${a.protein_id}|${a.temperature_c}`;
      if (seen.has(k)) continue;
      seen.add(k);
      (by[a.subcluster] ??= []).push({ t: a.temperature_c, name: a.protein_name });
    }
    return sortGroups(Object.keys(by)).map((g) => {
      const v = by[g].map((x) => x.t).sort((a, b) => a - b);
      const q = (p: number) => v[Math.min(v.length - 1, Math.floor(p * (v.length - 1) + 0.5))];
      return { g, pts: by[g], median: q(0.5), q1: q(0.25), q3: q(0.75), proteins: new Set(by[g].map((x) => x.name)).size };
    });
  }, [assays]);
  const [hover, setHover] = useState<string | null>(null);

  if (!data.length) return <p className="py-10 text-center text-sm text-muted">No detected-activity temperatures in the current filter.</p>;
  const W = 640;
  const H = 420;
  const pad = { l: 40, r: 12, t: 24, b: 30 };
  const tMin = 0;
  const tMax = 100;
  const y = (t: number) => pad.t + (1 - (t - tMin) / (tMax - tMin)) * (H - pad.t - pad.b);
  const bw = (W - pad.l - pad.r) / data.length;
  const jitter = (s: string) => {
    let h = 0;
    for (const c of s) h = (h * 31 + c.charCodeAt(0)) | 0;
    return ((h % 1000) / 1000 - 0.5) * 0.55;
  };

  return (
    <div>
      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[560px]" role="img" aria-label="Temperatures with detected PET activity by subgroup">
          {[20, 40, 60, 80, 100].map((t) => (
            <g key={t}>
              <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="#294157" strokeOpacity={0.5} strokeDasharray="2 4" />
              <text x={pad.l - 6} y={y(t) + 3} textAnchor="end" fontSize={10} fill="#9BB3C6" fontFamily="var(--font-geist-mono)">
                {t}°
              </text>
            </g>
          ))}
          {data.map((d, i) => {
            const cx = pad.l + bw * (i + 0.5);
            const c = clusterColor(d.g);
            return (
              <g key={d.g} onMouseEnter={() => setHover(d.g)} onMouseLeave={() => setHover(null)}>
                <rect x={cx - bw * 0.3} y={y(d.q3)} width={bw * 0.6} height={Math.max(1, y(d.q1) - y(d.q3))} rx={4} fill={c} fillOpacity={0.12} stroke={c} strokeOpacity={0.35} />
                {d.pts.map((p, j) => (
                  <circle key={j} cx={cx + jitter(p.name + p.t) * bw} cy={y(p.t)} r={2.6} fill={c} fillOpacity={hover && hover !== d.g ? 0.2 : 0.75}>
                    <title>{`${p.name}: ${p.t} °C`}</title>
                  </circle>
                ))}
                <line x1={cx - bw * 0.32} x2={cx + bw * 0.32} y1={y(d.median)} y2={y(d.median)} stroke="#F0F8FF" strokeWidth={2} />
                <text x={cx} y={H - 12} textAnchor="middle" fontSize={11} fill={c} fontFamily="var(--font-geist-mono)">
                  {d.g}
                </text>
                <text x={cx} y={14} textAnchor="middle" fontSize={9} fill="#9BB3C6" fontFamily="var(--font-geist-mono)">
                  n={d.proteins}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-muted">
        One dot per protein × temperature at which PET breakdown was detected; box = interquartile range, white line = median, n = proteins. These are temperatures that
        researchers chose to test, not optima. Small subgroups (n &lt; 5) carry little weight.
      </p>
    </div>
  );
}

/** Simple horizontal bar of counts. */
export function CountBars({ rows, color = "#4CA8D8", unitLabel }: { rows: { label: string; detected: number; other: number }[]; color?: string; unitLabel: string }) {
  const max = Math.max(1, ...rows.map((r) => r.detected + r.other));
  return (
    <div className="flex flex-col gap-2">
      {rows.map((r) => (
        <div key={r.label} className="grid grid-cols-[minmax(90px,150px)_1fr_auto] items-center gap-3 text-xs">
          <span className="truncate text-muted" title={r.label}>
            {r.label}
          </span>
          <div className="flex h-2.5 overflow-hidden rounded-full bg-line/40">
            <div style={{ width: `${(100 * r.detected) / max}%`, background: OUTCOME_COLORS.detected }} title={`${r.detected} detected`} />
            <div style={{ width: `${(100 * r.other) / max}%`, background: color, opacity: 0.5 }} title={`${r.other} other outcomes`} />
          </div>
          <span className="tabular w-20 text-right font-mono text-ink">
            {r.detected + r.other} <span className="text-muted">{unitLabel}</span>
          </span>
        </div>
      ))}
    </div>
  );
}

/** Values measured across temperatures within one comparable series (same paper, metric, unit, pH, duration, loading). */
export function SeriesChart({ series, names }: { series: TemperatureSeries[]; names: Map<number, string> }) {
  const proteins = useMemo(() => [...new Set(series.map((s) => s.protein_id))].sort((a, b) => (names.get(a) ?? "").localeCompare(names.get(b) ?? "")), [series, names]);
  const [pid, setPid] = useState<number>(proteins[0]);
  const [idx, setIdx] = useState(0);
  const mine = series.filter((s) => s.protein_id === (proteins.includes(pid) ? pid : proteins[0]));
  const s = mine[Math.min(idx, mine.length - 1)];
  if (!s) return <p className="py-10 text-center text-sm text-muted">No comparable temperature series in the current filter.</p>;
  const rows = s.temperatures.map((t, i) => ({ t, v: s.values[i] }));
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Select label="Protein" value={String(pid)} onChange={(v) => { setPid(Number(v)); setIdx(0); }} options={proteins.map((p) => ({ value: String(p), label: names.get(p) ?? String(p) }))} />
        <Select
          label="Series"
          value={String(Math.min(idx, mine.length - 1))}
          onChange={(v) => setIdx(Number(v))}
          options={mine.map((m, i) => ({ value: String(i), label: `${i + 1}. ${m.metric} (${m.unit})${m.ph != null ? `, pH ${m.ph}` : ""}` }))}
        />
      </div>
      <div className="h-[260px]">
        <ResponsiveContainer>
          <LineChart data={rows} margin={{ top: 16, right: 16, bottom: 22, left: 0 }}>
            <CartesianGrid {...gridProps} />
            <XAxis dataKey="t" type="number" domain={["dataMin - 2", "dataMax + 2"]} {...axisProps} ticks={s.temperatures} label={{ value: "Temperature (°C)", position: "bottom", fill: "#9BB3C6", fontSize: 11 }} />
            <YAxis {...axisProps} label={{ value: s.unit, angle: -90, position: "insideLeft", fill: "#9BB3C6", fontSize: 11 }} />
            <ReferenceLine x={s.best_tested_temperature_c} stroke="#E8B56B" strokeDasharray="4 4" label={{ value: "best tested", fill: "#E8B56B", fontSize: 10, position: "top" }} />
            <Tooltip content={({ payload }) => (payload?.length ? <ChartTooltip title={`${payload[0].payload.t} °C`} rows={[{ label: s.metric, value: `${payload[0].payload.v} ${s.unit}`, color: "#48E1CD" }]} /> : null)} />
            <Line dataKey="v" stroke="#48E1CD" strokeWidth={2} dot={{ r: 4, fill: "#091321", stroke: "#48E1CD", strokeWidth: 2 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-muted">
        Best of the <b className="text-ink">tested</b> temperatures within one protocol ({s.best_at_edge}
        {s.best_at_edge !== "interior" && " — the true optimum may lie outside the tested range"}). Source:{" "}
        <a className="text-cyan hover:underline" href={`https://doi.org/${s.doi}`} target="_blank" rel="noreferrer">
          {s.doi}
        </a>
        {s.context && ` · ${s.context}`}
      </p>
    </div>
  );
}
