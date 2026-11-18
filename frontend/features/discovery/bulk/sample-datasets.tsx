"use client";

import { Database, Download, FlaskConical, Loader2, Play } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, Panel, PanelHeader, Skeleton } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { C, tint } from "@/lib/palette";
import type { SampleDataset } from "@/types/api";

// Accent per card is decorative only (it is not an evidence colour).
const ACCENTS = [C.aqua, C.sky, C.violet];

export function SampleDatasets({
  busyId,
  disabled,
  onAnalyse,
}: {
  busyId: string | null;
  disabled: boolean;
  onAnalyse: (s: SampleDataset) => void;
}) {
  const res = useApi<SampleDataset[]>("/batch/samples");

  return (
    <Panel>
      <PanelHeader
        eyebrow="Sample data"
        title="Try Sample Protein Datasets"
        description="Each sample is an ordinary CSV file. Analyse Dataset sends it through exactly the same bulk-analysis pipeline as an uploaded file; nothing is pre-computed."
        action={<Database className="size-4 text-muted" aria-hidden />}
      />
      <div className="p-5">
        {res.error ? (
          <ErrorState message={res.error.message} onRetry={res.retry} />
        ) : !res.data ? (
          <div className="grid gap-4 md:grid-cols-3" aria-busy="true">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-56 rounded-xl" label="Loading sample dataset" />
            ))}
          </div>
        ) : res.data.length === 0 ? (
          <EmptyState title="No sample datasets found">The sample CSV files are expected in data/samples on the server.</EmptyState>
        ) : (
          <div className="grid gap-4 md:grid-cols-3">
            {res.data.map((s, i) => {
              const accent = ACCENTS[i % ACCENTS.length];
              const busy = busyId === s.id;
              return (
                <article
                  key={s.id}
                  className="group relative flex flex-col overflow-hidden rounded-xl border border-line/70 bg-void/40 p-4 transition duration-200 hover:-translate-y-0.5 hover:border-electric/50 hover:shadow-[0_8px_30px_-12px_var(--glow-strong)] motion-reduce:transform-none"
                >
                  <div className="absolute inset-x-0 top-0 h-1" style={{ background: `linear-gradient(90deg, ${accent}, ${tint(accent, 10)})` }} aria-hidden />
                  <div className="flex items-center gap-2">
                    <span
                      className="grid size-8 place-items-center rounded-lg font-mono text-sm font-semibold"
                      style={{ background: tint(accent, 14), color: accent }}
                      aria-hidden
                    >
                      {s.number}
                    </span>
                    <span className="eyebrow">Dataset {s.number}</span>
                    <span className="tabular ml-auto font-mono text-[11px] text-muted">{s.n_proteins} proteins</span>
                  </div>
                  <h4 className="mt-3 text-[15px] font-semibold leading-snug tracking-tight text-ink">{s.title}</h4>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{s.description}</p>
                  <ul className="mt-3 flex flex-wrap gap-1.5" aria-label="Proteins in this dataset">
                    {s.proteins.map((p) => (
                      <li key={p} className="inline-flex items-center gap-1 rounded-md border border-line/70 bg-elevated/50 px-2 py-0.5 font-mono text-[11px] text-ink/85">
                        <FlaskConical className="size-3 text-muted" aria-hidden /> {p}
                      </li>
                    ))}
                  </ul>
                  <div className="mt-auto flex flex-wrap gap-2 pt-4">
                    <Button
                      size="sm"
                      variant="primary"
                      className="pulse-glow"
                      style={{ "--pulse-color": accent } as React.CSSProperties}
                      disabled={disabled}
                      onClick={() => onAnalyse(s)}
                      aria-label={`Analyse dataset ${s.number}: ${s.title}`}
                    >
                      {busy ? <Loader2 className="animate-spin" /> : <Play />}
                      {busy ? "Starting…" : "Analyse Dataset"}
                    </Button>
                    <Button asChild size="sm" variant="secondary">
                      <a href={s.download_url} download={s.filename} aria-label={`Download ${s.filename}`}>
                        <Download /> Download CSV
                      </a>
                    </Button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </Panel>
  );
}
