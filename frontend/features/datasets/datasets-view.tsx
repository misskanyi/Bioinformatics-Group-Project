"use client";

import { AlertTriangle, ArrowRight, CheckCircle2, ChevronDown, Download, ExternalLink, XCircle } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ErrorState, InfoTip, Panel, PanelHeader, Skeleton } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { cn, doiUrl, num } from "@/lib/utils";
import type { Datasets } from "@/types/api";

const COVERAGE_LABELS: Record<string, { label: string; tip: string }> = {
  with_temperature: { label: "Assay temperature reported", tip: "At least one PET assay with a temperature." },
  with_ph: { label: "Assay pH reported", tip: "At least one PET assay with a pH." },
  with_organism: { label: "Documented organism", tip: "Identical or precursor/mature-form database sequence." },
  with_plasticdb_record: { label: "Identical PlasticDB record", tip: "Exact sequence match to PlasticDB.fasta." },
  in_standardised_screen: { label: "In a standardised screen", tip: "Tested in a single-protocol screening table, comparable across proteins." },
};

function Pipeline({ steps }: { steps: Datasets["pipeline"] }) {
  return (
    <div className="grid gap-3 lg:grid-cols-5">
      {steps.map((s, i) => (
        <motion.div
          key={s.stage}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.08 }}
          className="relative rounded-xl border border-line/70 bg-void/50 p-4"
        >
          <div className="flex items-center justify-between">
            <span className="font-mono text-[11px] text-teal">0{i + 1}</span>
            {i < steps.length - 1 && <ArrowRight className="absolute -right-3 top-1/2 z-10 hidden size-5 -translate-y-1/2 rounded-full bg-surface text-teal lg:block" />}
          </div>
          <div className="mt-2 font-medium">{s.stage}</div>
          <div className="tabular mt-1 font-mono text-xs text-teal">{s.count}</div>
          <p className="mt-2 text-xs leading-relaxed text-muted">{s.detail}</p>
        </motion.div>
      ))}
    </div>
  );
}

export function DatasetsView() {
  const res = useApi<Datasets>("/datasets");
  const [showRefs, setShowRefs] = useState(false);
  const [showQuality, setShowQuality] = useState(false);
  if (res.error)
    return (
      <Panel>
        <ErrorState message={res.error.message} onRetry={res.retry} />
      </Panel>
    );
  const d = res.data;
  if (!d)
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-56 rounded-[14px]" />
        <Skeleton className="h-96 rounded-[14px]" />
      </div>
    );
  const total = d.coverage.proteins;
  const loo = Object.entries(d.leave_one_out.bands).sort((a, b) => b[1] - a[1]);

  return (
    <div className="flex flex-col gap-6">
      <Panel>
        <PanelHeader eyebrow="Research provenance" title="How the results were produced" description="Every number in this application traces back through these stages to the six original downloads." />
        <div className="p-5">
          <Pipeline steps={d.pipeline} />
        </div>
      </Panel>

      <div className="grid gap-6 xl:grid-cols-[1.3fr_1fr]">
        <Panel>
          <PanelHeader eyebrow="Dataset sources" title="Original files" description="Read-only inputs in data/. Record counts are as downloaded." />
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[620px] text-left text-xs">
              <thead>
                <tr className="text-muted">
                  {["File", "Format", "Records", "Duplicate seqs", "Notes"].map((h) => (
                    <th key={h} className="border-b border-line px-5 py-2 font-normal">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {d.inventory.map((r) => (
                  <tr key={r.file} className="border-b border-line/40 align-top">
                    <td className="max-w-[180px] break-all px-5 py-2.5 font-mono text-ink">{r.file}</td>
                    <td className="px-5 py-2.5 text-muted">{r.format}</td>
                    <td className="tabular px-5 py-2.5 font-mono">{num(r.records)}</td>
                    <td className="tabular px-5 py-2.5 font-mono">{r.duplicate_sequences ?? "—"}</td>
                    <td className="min-w-[240px] px-5 py-2.5 text-muted">{r.notes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel>
          <PanelHeader eyebrow="Annotation coverage" title={`Of the ${total} usable PET-active proteins`} />
          <div className="flex flex-col gap-3 p-5">
            {Object.entries(COVERAGE_LABELS).map(([k, { label, tip }]) => {
              const v = d.coverage[k] ?? 0;
              const missing = total - v;
              return (
                <div key={k}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5 text-muted">
                      {label} <InfoTip content={tip} />
                    </span>
                    <span className="tabular font-mono">
                      <span className="text-teal">{v}</span> <span className="text-muted">/ {total}</span>
                      {missing > 0 && <span className="ml-2 text-amber">{missing} missing</span>}
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-amber/20">
                    <motion.div className="h-full rounded-full bg-teal" initial={{ width: 0 }} animate={{ width: `${(100 * v) / total}%` }} transition={{ duration: 0.7 }} />
                  </div>
                </div>
              );
            })}
            <div className="mt-2 grid grid-cols-2 gap-3 border-t border-line/60 pt-4 text-xs">
              <div>
                <div className="text-muted">Duplicate sequences</div>
                <div className="font-mono text-lg text-teal">{d.coverage.duplicate_sequences}</div>
              </div>
              <div>
                <div className="text-muted">Usable PET-inactive sequences</div>
                <div className="font-mono text-lg text-amber">0 usable</div>
              </div>
            </div>
          </div>
        </Panel>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Panel>
          <PanelHeader eyebrow="Quality control" title="Checks on the cleaned protein set" />
          <ul className="flex flex-col gap-2 p-5">
            {d.qc_checks.map((c) => (
              <li key={c.check} className="flex items-center gap-3 text-sm">
                {c.passed ? <CheckCircle2 className="size-4 shrink-0 text-mint" /> : <XCircle className="size-4 shrink-0 text-rose" />}
                <span className="flex-1">{c.check}</span>
                <span className="tabular font-mono text-muted">{c.value}</span>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel>
          <PanelHeader
            eyebrow="Matching sanity check"
            title="Leave-one-out nearest neighbour"
            description={`${d.leave_one_out.description} Median identity to the nearest other protein: ${(d.leave_one_out.median_identity * 100).toFixed(0)}%.`}
          />
          <div className="flex flex-col gap-2 p-5">
            {loo.map(([band, n]) => (
              <div key={band} className="grid grid-cols-[1fr_auto] items-center gap-3 text-xs">
                <div>
                  <div className="text-muted">{band}</div>
                  <div className="mt-1 h-2 overflow-hidden rounded-full bg-line/40">
                    <div className="h-full rounded-full bg-cyan" style={{ width: `${(100 * n) / total}%` }} />
                  </div>
                </div>
                <span className="tabular font-mono">{n}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <Panel>
        <button onClick={() => setShowQuality((s) => !s)} className="flex w-full items-center justify-between p-5 text-left" aria-expanded={showQuality}>
          <div>
            <div className="eyebrow mb-1">Feasibility analysis</div>
            <div className="text-[15px] font-semibold">Full quality metrics ({d.quality.length})</div>
            <p className="mt-1 text-[13px] text-muted">Assay classification counts and how each was calculated.</p>
          </div>
          <ChevronDown className={cn("size-5 text-muted transition", showQuality && "rotate-180")} />
        </button>
        {showQuality && (
          <div className="overflow-x-auto border-t border-line/60">
            <table className="w-full min-w-[640px] text-left text-xs">
              <tbody>
                {d.quality.map((q) => (
                  <tr key={q.metric} className="border-b border-line/40 align-top">
                    <td className="px-5 py-2 text-ink">{q.metric}</td>
                    <td className="tabular px-5 py-2 font-mono text-teal">{q.value}</td>
                    <td className="max-w-md px-5 py-2 text-muted">{q.how_calculated}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <div className="grid gap-6 xl:grid-cols-2">
        <Panel>
          <PanelHeader eyebrow="Limitations" title="What this data cannot support" />
          <ul className="flex flex-col gap-3 p-5">
            {d.limitations.map((l) => (
              <li key={l} className="flex gap-3 text-sm leading-relaxed text-ink/90">
                <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber" />
                {l}
              </li>
            ))}
          </ul>
        </Panel>
        <Panel>
          <PanelHeader eyebrow="Downloads" title="Processed datasets" description="CSV / FASTA files generated by the analysis pipeline." />
          <div className="flex flex-col gap-1.5 p-5">
            {d.downloads.map((f) => (
              <div key={f.key} className="flex items-center justify-between gap-3 rounded-lg px-2 py-1.5 transition hover:bg-elevated/50">
                <div className="min-w-0">
                  <div className="truncate font-mono text-xs text-ink">{f.file}</div>
                  <div className="truncate text-[11px] text-muted">{f.description}</div>
                </div>
                {f.available ? (
                  <Button asChild size="sm" variant="ghost">
                    <a href={`/api/downloads/${f.key}`} download aria-label={`Download ${f.file}`}>
                      <Download />
                    </a>
                  </Button>
                ) : (
                  <span className="text-[11px] text-amber">not generated</span>
                )}
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <Panel>
        <button onClick={() => setShowRefs((s) => !s)} className="flex w-full items-center justify-between p-5 text-left" aria-expanded={showRefs}>
          <div>
            <div className="eyebrow mb-1">Research references</div>
            <div className="text-[15px] font-semibold">{d.references.length} publications behind the PET assays</div>
            <p className="mt-1 text-[13px] text-muted">Sorted by the number of reference proteins each paper characterises.</p>
          </div>
          <ChevronDown className={cn("size-5 text-muted transition", showRefs && "rotate-180")} />
        </button>
        {showRefs && (
          <div className="grid gap-x-6 gap-y-1 border-t border-line/60 p-5 md:grid-cols-2 xl:grid-cols-3">
            {d.references.map((r) => (
              <a key={r.doi} href={doiUrl(r.doi)} target="_blank" rel="noreferrer" className="flex items-center justify-between gap-3 rounded-md px-2 py-1 text-xs transition hover:bg-elevated/60">
                <span className="truncate font-mono text-cyan">{r.doi}</span>
                <span className="flex shrink-0 items-center gap-1 text-muted">
                  {r.n_proteins} <ExternalLink className="size-3" />
                </span>
              </a>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
