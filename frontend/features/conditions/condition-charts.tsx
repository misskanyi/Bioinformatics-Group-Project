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
import { axisLabel, axisProps, barCursor, ChartInView, ChartTooltip, gridProps, Legend, useChartMotion } from "@/components/viz/chart-kit";
import { C, CHART, clusterColor, OUTCOME_COLORS, OUTCOME_LABELS } from "@/lib/palette";
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
  const motion = useChartMotion(rows, 650);
  const [hidden, setHidden] = useState<Set<string>>(new Set());

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
      <ChartInView className="chart-hl h-[300px]">
        <ResponsiveContainer>
          <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 22, left: 0 }}>
            <CartesianGrid {...gridProps} vertical={false} />
            <XAxis dataKey="bin" {...axisProps} label={axisLabel("Assay temperature (°C, 5 °C bins)")} />
            <YAxis {...axisProps} allowDecimals={false} width={52} label={axisLabel(unit === "proteins" ? "Distinct proteins" : "Assay records", "insideLeft")} />
            <Tooltip
              cursor={barCursor}
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
            {OUTCOMES.filter((o) => !hidden.has(o)).map((o, i, shown) => (
              <Bar key={o} dataKey={o} stackId="t" fill={OUTCOME_COLORS[o]} radius={i === shown.length - 1 ? [3, 3, 0, 0] : 0} {...motion} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </ChartInView>
      <Legend
        items={OUTCOMES.map((o) => ({ key: o, label: OUTCOME_LABELS[o], color: OUTCOME_COLORS[o] }))}
        hidden={hidden}
        onToggle={(o) =>
          setHidden((h) => {
            const n = new Set(h);
            if (n.has(o)) n.delete(o);
            else n.add(o);
            return n;
          })
        }
      />
      <p className="mt-1 text-[11px] text-muted">Click an outcome in the legend to hide or show it.</p>
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
  const pad = { l: 52, r: 12, t: 24, b: 30 };
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
          <text transform={`translate(12 ${(pad.t + H - pad.b) / 2}) rotate(-90)`} textAnchor="middle" fontSize={10} fill={CHART.axis}>
            Assay temperature (°C)
          </text>
          {[20, 40, 60, 80, 100].map((t) => (
            <g key={t}>
              <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="var(--chart-grid)" strokeOpacity={0.5} strokeDasharray="2 4" />
              <text x={pad.l - 6} y={y(t) + 3} textAnchor="end" fontSize={10} fill="var(--color-muted)" fontFamily="var(--font-geist-mono)">
                {t}°
              </text>
            </g>
          ))}
          {data.map((d, i) => {
            const cx = pad.l + bw * (i + 0.5);
            const c = clusterColor(d.g);
            return (
              <g
                key={d.g}
                className="reveal"
                style={{ animationDelay: `${i * 60}ms` }}
                onMouseEnter={() => setHover(d.g)}
                onMouseLeave={() => setHover(null)}
              >
                <rect
                  className="chart-mark"
                  x={cx - bw * 0.3}
                  y={y(d.q3)}
                  width={bw * 0.6}
                  height={Math.max(1, y(d.q1) - y(d.q3))}
                  rx={4}
                  fill={c}
                  fillOpacity={hover === d.g ? 0.22 : 0.12}
                  stroke={c}
                  strokeOpacity={hover && hover !== d.g ? 0.15 : 0.35}
                />
                {d.pts.map((p, j) => (
                  <circle key={j} className="chart-mark" cx={cx + jitter(p.name + p.t) * bw} cy={y(p.t)} r={hover === d.g ? 3 : 2.6} fill={c} fillOpacity={hover && hover !== d.g ? 0.15 : 0.75}>
                    <title>{`${p.name}: ${p.t} °C`}</title>
                  </circle>
                ))}
                <line x1={cx - bw * 0.32} x2={cx + bw * 0.32} y1={y(d.median)} y2={y(d.median)} stroke="var(--color-ink)" strokeWidth={2} />
                <text x={cx} y={H - 12} textAnchor="middle" fontSize={11} fill={c} fontFamily="var(--font-geist-mono)">
                  {d.g}
                </text>
                <text x={cx} y={14} textAnchor="middle" fontSize={9} fill="var(--color-muted)" fontFamily="var(--font-geist-mono)">
                  n={d.proteins}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-muted">
        One dot per protein × temperature at which PET breakdown was detected; box = interquartile range, bold line = median, n = proteins. Hover a subgroup to
        highlight it. These are temperatures that
        researchers chose to test, not optima. Small subgroups (n &lt; 5) carry little weight.
      </p>
    </div>
  );
}

/** Simple horizontal bar of counts. */
export function CountBars({ rows, color = C.sky, unitLabel }: { rows: { label: string; detected: number; other: number }[]; color?: string; unitLabel: string }) {
  const max = Math.max(1, ...rows.map((r) => r.detected + r.other));
  return (
    <div className="flex flex-col gap-2">
      {rows.map((r) => (
        <div key={r.label} className="grid grid-cols-[minmax(90px,150px)_1fr_auto] items-center gap-3 text-xs">
          <span className="truncate text-muted" title={r.label}>
            {r.label}
          </span>
          <div className="h-2.5 overflow-hidden rounded-full bg-line/40">
            <div className="grow-x flex h-full">
              <div className="bar-fill" style={{ width: `${(100 * r.detected) / max}%`, background: OUTCOME_COLORS.detected }} title={`${r.detected} detected`} />
              <div className="bar-fill" style={{ width: `${(100 * r.other) / max}%`, background: color, opacity: 0.5 }} title={`${r.other} other outcomes`} />
            </div>
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
  return <SeriesBody s={s} rows={rows} proteins={proteins} pid={pid} setPid={setPid} idx={idx} setIdx={setIdx} mine={mine} names={names} />;
}

function SeriesBody({
  s,
  rows,
  proteins,
  pid,
  setPid,
  idx,
  setIdx,
  mine,
  names,
}: {
  s: TemperatureSeries;
  rows: { t: number; v: number }[];
  proteins: number[];
  pid: number;
  setPid: (v: number) => void;
  idx: number;
  setIdx: (v: number) => void;
  mine: TemperatureSeries[];
  names: Map<number, string>;
}) {
  // Redraw the line when another series is picked, not on hover rerenders.
  const motion = useChartMotion(s, 900);
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
      <ChartInView className="h-[260px]">
        <ResponsiveContainer>
          <LineChart data={rows} margin={{ top: 16, right: 16, bottom: 22, left: 4 }}>
            <CartesianGrid {...gridProps} />
            <XAxis dataKey="t" type="number" domain={["dataMin - 2", "dataMax + 2"]} {...axisProps} ticks={s.temperatures} label={axisLabel("Assay temperature (°C)")} />
            <YAxis {...axisProps} width={56} label={axisLabel(s.unit, "insideLeft")} />
            <ReferenceLine x={s.best_tested_temperature_c} stroke={C.amber} strokeDasharray="4 4" label={{ value: "best tested", fill: C.amber, fontSize: 10, position: "top" }} />
            <Tooltip
              cursor={{ stroke: CHART.grid, strokeDasharray: "3 3" }}
              content={({ payload }) =>
                payload?.length ? (
                  <ChartTooltip
                    title={`${payload[0].payload.t} °C`}
                    rows={[{ label: s.metric, value: `${payload[0].payload.v} ${s.unit}`, color: C.aqua }]}
                    note={payload[0].payload.t === s.best_tested_temperature_c ? "Best of the tested temperatures in this series" : "Measured value"}
                  />
                ) : null
              }
            />
            <Line
              type="linear"
              dataKey="v"
              stroke={C.aqua}
              strokeWidth={2}
              dot={{ r: 4, fill: CHART.dotBg, stroke: C.aqua, strokeWidth: 2 }}
              activeDot={{ r: 6, fill: C.aqua, stroke: CHART.dotBg, strokeWidth: 2 }}
              {...motion}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartInView>
      <p className="mt-1 text-[11px] text-muted">Dots are measured values; straight segments only join them and are not measurements in between.</p>
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
