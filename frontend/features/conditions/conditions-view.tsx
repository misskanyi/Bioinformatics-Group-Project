"use client";

import { ChevronLeft, ChevronRight, ExternalLink, Filter, RotateCcw, Search } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Badge, EmptyState, ErrorState, Input, Metric, Notice, Panel, PanelHeader, Select, Skeleton, Slider } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { clusterColor, OUTCOME_COLORS, OUTCOME_LABELS } from "@/lib/palette";
import { doiUrl, num, sortGroups } from "@/lib/utils";
import type { Assay, AssayOutcome, Conditions } from "@/types/api";

import { ClusterTemperatureStrip, CountBars, SeriesChart, TemperatureHistogram } from "./condition-charts";

const PAGE = 25;
const ALL = "__all";

function toAssays(c: Conditions): Assay[] {
  return c.assays.map((t) => Object.fromEntries(c.assay_fields.map((f, i) => [f, t[i]])) as unknown as Assay);
}

export function ConditionsView() {
  const res = useApi<Conditions>("/conditions");
  const all = useMemo(() => (res.data ? toAssays(res.data) : []), [res.data]);

  const [protein, setProtein] = useState(ALL);
  const [cluster, setCluster] = useState(ALL);
  const [form, setForm] = useState(ALL);
  const [outcome, setOutcome] = useState(ALL);
  const [range, setRange] = useState<[number, number]>([0, 100]);
  const [text, setText] = useState("");
  const [page, setPage] = useState(0);
  const q = useDeferredValue(text.trim().toLowerCase());

  const options = useMemo(() => {
    const names = new Map(all.map((a) => [a.protein_id, a.protein_name]));
    const forms = new Map<string, number>();
    all.forEach((a) => a.material_form && forms.set(a.material_form, (forms.get(a.material_form) ?? 0) + 1));
    return {
      names,
      proteins: [...names.entries()].sort((a, b) => a[1].localeCompare(b[1])),
      clusters: sortGroups([...new Set(all.map((a) => a.subcluster))]),
      forms: [...forms.entries()].sort((a, b) => b[1] - a[1]),
    };
  }, [all]);

  const filtered = useMemo(
    () =>
      all.filter(
        (a) =>
          (protein === ALL || a.protein_id === Number(protein)) &&
          (cluster === ALL || a.subcluster === cluster) &&
          (form === ALL || a.material_form === form) &&
          (outcome === ALL || a.degradation_detected === outcome) &&
          (range[0] === 0 && range[1] === 100 ? true : a.temperature_c != null && a.temperature_c >= range[0] && a.temperature_c <= range[1]) &&
          (!q ||
            a.protein_name.toLowerCase().includes(q) ||
            a.literature_doi.toLowerCase().includes(q) ||
            (a.material_name ?? "").toLowerCase().includes(q) ||
            (a.detection_methods ?? "").toLowerCase().includes(q)),
      ),
    [all, protein, cluster, form, outcome, range, q],
  );

  const stats = useMemo(() => {
    const prots = new Set(filtered.map((a) => a.protein_id));
    const det = filtered.filter((a) => a.degradation_detected === "detected").length;
    const papers = new Set(filtered.map((a) => a.literature_doi)).size;
    const ph = new Map<string, { d: number; o: number }>();
    const forms = new Map<string, { d: number; o: number }>();
    for (const a of filtered) {
      const pk = a.ph == null ? "Not reported" : `pH ${Math.round(a.ph)}`;
      const fk = a.material_form ?? "Not reported";
      for (const [m, k] of [[ph, pk], [forms, fk]] as const) {
        const r = m.get(k) ?? { d: 0, o: 0 };
        if (a.degradation_detected === "detected") r.d++;
        else r.o++;
        m.set(k, r);
      }
    }
    const rows = (m: Map<string, { d: number; o: number }>) => [...m.entries()].map(([label, r]) => ({ label, detected: r.d, other: r.o }));
    return {
      proteins: prots.size,
      detected: det,
      papers,
      ph: rows(ph).sort((a, b) => (a.label === "Not reported" ? 1 : b.label === "Not reported" ? -1 : parseFloat(a.label.slice(3)) - parseFloat(b.label.slice(3)))),
      forms: rows(forms).sort((a, b) => b.detected + b.other - (a.detected + a.other)).slice(0, 8),
    };
  }, [filtered]);

  const series = useMemo(() => {
    const ids = new Set(filtered.map((a) => a.protein_id));
    return (res.data?.series ?? []).filter((s) => ids.has(s.protein_id));
  }, [filtered, res.data]);

  const summary = protein !== ALL ? res.data?.proteins.find((p) => p.protein_id === Number(protein)) : undefined;
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE));
  const rows = filtered.slice(page * PAGE, page * PAGE + PAGE);
  const perProtein = useMemo(() => {
    const m = new Map<number, number>();
    filtered.forEach((a) => m.set(a.protein_id, (m.get(a.protein_id) ?? 0) + 1));
    return m;
  }, [filtered]);

  const resetAll = () => {
    setProtein(ALL);
    setCluster(ALL);
    setForm(ALL);
    setOutcome(ALL);
    setRange([0, 100]);
    setText("");
    setPage(0);
  };
  const set = <T,>(f: (v: T) => void) => (v: T) => {
    f(v);
    setPage(0);
  };

  if (res.error)
    return (
      <Panel>
        <ErrorState message={res.error.message} onRetry={res.retry} />
      </Panel>
    );
  if (!res.data)
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-28 rounded-[14px]" />
        <div className="grid gap-6 xl:grid-cols-2">
          <Skeleton className="h-96 rounded-[14px]" />
          <Skeleton className="h-96 rounded-[14px]" />
        </div>
      </div>
    );

  return (
    <div className="flex flex-col gap-6">
      <Notice>
        Temperatures here are the conditions researchers <b>chose to test</b>. The highest temperature with activity is not treated as an optimum; a “best tested
        temperature” is shown only within one comparable series of ≥ 3 temperatures.
      </Notice>

      {/* filters */}
      <Panel className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex items-center gap-2 pb-2 text-xs text-muted">
            <Filter className="size-4 text-teal" /> Filters
          </div>
          <Select className="w-44" label="Protein" value={protein} onChange={set(setProtein)} options={[{ value: ALL, label: "All proteins" }, ...options.proteins.map(([id, n]) => ({ value: String(id), label: n }))]} />
          <Select className="w-36" label="Subgroup" value={cluster} onChange={set(setCluster)} options={[{ value: ALL, label: "All subgroups" }, ...options.clusters.map((c) => ({ value: c, label: `Subgroup ${c}` }))]} />
          <Select className="w-44" label="PET material form" value={form} onChange={set(setForm)} options={[{ value: ALL, label: "All material forms" }, ...options.forms.map(([f, n]) => ({ value: f, label: `${f} (${n})` }))]} />
          <Select
            className="w-52"
            label="Detection result"
            value={outcome}
            onChange={set(setOutcome)}
            options={[{ value: ALL, label: "All results" }, ...(["detected", "not detected", "unclear", "excluded"] as AssayOutcome[]).map((o) => ({ value: o, label: OUTCOME_LABELS[o] }))]}
          />
          <div className="w-full sm:w-56">
            <div className="mb-1.5 flex justify-between text-xs">
              <span className="text-muted">Temperature</span>
              <span className="font-mono text-teal">
                {range[0]}–{range[1]} °C
              </span>
            </div>
            <Slider min={0} max={100} step={1} value={range} onValueChange={(v) => set(setRange)([v[0], v[1]])} aria-label="Temperature range" />
          </div>
          <Button size="sm" variant="ghost" onClick={resetAll} className="ml-auto">
            <RotateCcw /> Reset
          </Button>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-4 border-t border-line/60 pt-4 sm:grid-cols-4">
          <Metric label="Assay records" value={num(filtered.length)} hint={`of ${num(all.length)}`} />
          <Metric label="Distinct proteins" value={num(stats.proteins)} accent="#4CA8D8" />
          <Metric label="Breakdown detected" value={filtered.length ? `${Math.round((100 * stats.detected) / filtered.length)}%` : "—"} accent="#69E8C3" hint="of assay records" />
          <Metric label="Publications" value={num(stats.papers)} accent="#B49CF5" />
        </div>
      </Panel>

      {filtered.length === 0 ? (
        <Panel>
          <EmptyState title="No assays match these filters">Widen the temperature range or clear a filter.</EmptyState>
        </Panel>
      ) : (
        <>
          {summary && (
            <Panel glow className="p-5">
              <div className="eyebrow">Protein-specific observations</div>
              <div className="mt-1 flex flex-wrap items-baseline gap-3">
                <h3 className="font-mono text-xl font-semibold">{summary.protein_name}</h3>
                <span className="font-mono text-xs" style={{ color: clusterColor(summary.subcluster) }}>
                  {summary.subcluster}
                </span>
              </div>
              <div className="mt-3 grid gap-4 text-sm sm:grid-cols-3">
                <div>
                  <div className="text-xs text-muted">Temperatures tested</div>
                  <div className="font-mono">{summary.temperatures_tested_c ?? "—"} °C</div>
                </div>
                <div>
                  <div className="text-xs text-muted">Breakdown detected at</div>
                  <div className="font-mono text-mint">{summary.temperatures_with_activity_c ?? "—"} °C</div>
                </div>
                <div>
                  <div className="text-xs text-muted">Tested, none detected at</div>
                  <div className="font-mono text-rose">{summary.temperatures_without_detected_activity_c || "—"}</div>
                </div>
              </div>
              <p className="mt-3 text-sm text-muted">
                <Badge color="#E8B56B" dot={false}>
                  Optimum status
                </Badge>{" "}
                {summary.temperature_optimum_status}
              </p>
            </Panel>
          )}

          <div className="grid gap-6 xl:grid-cols-2">
            <Panel>
              <PanelHeader eyebrow="Temperature distribution" title="Reported assay temperatures" />
              <div className="p-5">
                <TemperatureHistogram assays={filtered} />
              </div>
            </Panel>
            <Panel>
              <PanelHeader eyebrow="Cluster comparison" title="Temperatures with detected breakdown, by subgroup" />
              <div className="p-5">
                <ClusterTemperatureStrip assays={filtered} />
              </div>
            </Panel>
          </div>

          <div className="grid gap-6 xl:grid-cols-3">
            <Panel>
              <PanelHeader eyebrow="pH" title="Reported assay pH" description="Bars: assays with detected breakdown (green) vs. other outcomes." />
              <div className="p-5">
                <CountBars rows={stats.ph} unitLabel="assays" />
              </div>
            </Panel>
            <Panel>
              <PanelHeader eyebrow="Substrate" title="PET material form" description="Top forms in the current selection." />
              <div className="p-5">
                <CountBars rows={stats.forms} color="#B49CF5" unitLabel="assays" />
              </div>
            </Panel>
            <Panel>
              <PanelHeader eyebrow="Comparable series" title="Activity across tested temperatures" />
              <div className="p-5">
                <SeriesChart key={protein + cluster} series={series} names={options.names} />
              </div>
            </Panel>
          </div>
        </>
      )}

      {/* evidence table */}
      <Panel>
        <PanelHeader
          eyebrow="Evidence table"
          title="Experimental records"
          description="One row per reported assay. Rows for the same protein are repeated measurements under different conditions, not independent proteins."
          action={
            <div className="relative w-64">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
              <Input value={text} onChange={(e) => set(setText)(e.target.value)} placeholder="Search protein, DOI, method…" className="pl-8" aria-label="Search assays" />
            </div>
          }
        />
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[980px] text-left text-xs">
            <thead className="sticky top-0 bg-surface">
              <tr className="text-muted">
                {["Protein", "Temp", "pH", "Result", "Measurement method", "Substrate", "Publication"].map((h) => (
                  <th key={h} className="border-b border-line px-4 py-2.5 font-normal">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((a, i) => (
                <tr key={`${page}-${i}`} className="border-b border-line/40 align-top transition hover:bg-elevated/40">
                  <td className="px-4 py-2.5">
                    <div className="font-mono text-ink">{a.protein_name}</div>
                    <div className="font-mono text-[10px] text-muted">
                      ID {a.protein_id} · <span style={{ color: clusterColor(a.subcluster) }}>{a.subcluster}</span> · {perProtein.get(a.protein_id)} rows
                    </div>
                  </td>
                  <td className="tabular px-4 py-2.5 font-mono">{a.temperature_c ?? "—"}{a.temperature_c != null && " °C"}</td>
                  <td className="tabular px-4 py-2.5 font-mono">{a.ph ?? "—"}</td>
                  <td className="px-4 py-2.5">
                    <Badge color={OUTCOME_COLORS[a.degradation_detected]}>{a.degradation_detected}</Badge>
                    {a.outcome_reason && <div className="mt-1 max-w-[180px] text-[10px] text-muted">{a.outcome_reason}</div>}
                  </td>
                  <td className="max-w-[260px] px-4 py-2.5 text-muted">
                    <div className="line-clamp-2" title={a.detection_methods ?? undefined}>
                      {a.detection_methods || "—"}
                    </div>
                    {a.metric_types && <div className="mt-0.5 font-mono text-[10px] text-cyan/80">{a.metric_types}</div>}
                  </td>
                  <td className="max-w-[220px] px-4 py-2.5">
                    <div className="text-ink">{a.material_form ?? "—"}</div>
                    <div className="line-clamp-1 text-[10px] text-muted" title={a.material_name ?? undefined}>
                      {a.material_name}
                      {a.crystallinity_percent != null && ` · ${a.crystallinity_percent}% crystallinity`}
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    <a href={doiUrl(a.literature_doi)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-mono text-cyan hover:text-teal hover:underline">
                      {a.literature_doi} <ExternalLink className="size-3" />
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!rows.length && <EmptyState title="No matching records" />}
        </div>
        <div className="flex items-center justify-between gap-3 px-4 py-3 text-xs text-muted">
          <span>
            {filtered.length ? `${page * PAGE + 1}–${Math.min(filtered.length, (page + 1) * PAGE)} of ${num(filtered.length)}` : "0 records"}
          </span>
          <div className="flex items-center gap-1">
            <Button size="icon" variant="ghost" disabled={page === 0} onClick={() => setPage((p) => p - 1)} aria-label="Previous page">
              <ChevronLeft />
            </Button>
            <span className="tabular font-mono">
              {page + 1} / {pages}
            </span>
            <Button size="icon" variant="ghost" disabled={page >= pages - 1} onClick={() => setPage((p) => p + 1)} aria-label="Next page">
              <ChevronRight />
            </Button>
          </div>
        </div>
      </Panel>

      <ul className="grid gap-2 text-xs leading-relaxed text-muted md:grid-cols-2">
        {res.data.notes.map((n) => (
          <li key={n} className="flex gap-2">
            <span className="mt-1.5 size-1 shrink-0 rounded-full bg-teal" /> {n}
          </li>
        ))}
      </ul>
    </div>
  );
}
