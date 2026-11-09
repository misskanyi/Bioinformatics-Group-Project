"use client";

import { RotateCcw, Square } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { DnaLoader } from "@/components/ui/dna-loader";
import { ErrorState, Panel } from "@/components/ui/primitives";
import { api, ApiError, useApi } from "@/lib/api";
import type { BatchJob, BatchLimits, BatchParse, BatchResult, ColumnMapping } from "@/types/api";

import { PredictionNotice } from "../evidence";
import { BatchCharts } from "./batch-charts";
import { PreviewStep } from "./preview-step";
import { ResultsTable } from "./results-table";
import { type Upload, UploadStep } from "./upload-step";

const POLL_MS = 700;

type Stage =
  | { name: "upload" }
  | { name: "preview"; upload: Upload; parse: BatchParse }
  | { name: "job"; upload: Upload; job: Omit<BatchJob, "results"> };

function Progress({ job, onCancel }: { job: Omit<BatchJob, "results">; onCancel: () => void }) {
  const ratio = job.total ? job.done / job.total : 0;
  const running = job.state === "queued" || job.state === "running";
  return (
    <Panel className="overflow-hidden p-5">
      <div className="flex flex-wrap items-center gap-5">
        {running && <DnaLoader small pairs={8} />}
        <div className="min-w-56 flex-1">
          <div className="flex items-baseline justify-between gap-3">
            <p className="font-medium">
              {job.state === "queued" && "Queued…"}
              {job.state === "running" && "Aligning and profiling sequences"}
              {job.state === "done" && "Batch complete"}
              {job.state === "cancelled" && "Batch cancelled"}
            </p>
            <span className="tabular font-mono text-xs text-muted">
              {job.done} / {job.total} records
            </span>
          </div>
          <div
            role="progressbar"
            aria-label="Batch progress"
            aria-valuemin={0}
            aria-valuemax={job.total}
            aria-valuenow={job.done}
            className="mt-2 h-2 overflow-hidden rounded-full bg-line/50"
          >
            <div
              className="h-full rounded-full bg-gradient-to-r from-electric to-cyan shadow-[0_0_12px_var(--color-cyan)] transition-[width] duration-500 ease-out"
              style={{ width: `${100 * ratio}%` }}
            />
          </div>
          <p className="mt-1.5 text-xs text-muted">
            {job.meta.filename} · {job.meta.counts.valid} valid, {job.meta.counts.invalid} invalid, {job.meta.counts.duplicate} duplicate · Smith–Waterman against 298
            characterised proteins
          </p>
        </div>
        {running && (
          <Button size="sm" variant="ghost" onClick={onCancel}>
            <Square /> Cancel
          </Button>
        )}
      </div>
    </Panel>
  );
}

export function BulkAnalysis() {
  const limits = useApi<BatchLimits>("/batch/limits");
  const [stage, setStage] = useState<Stage>({ name: "upload" });
  const [results, setResults] = useState<BatchResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const live = useRef<string | null>(null); // id of the job being polled

  const parse = useCallback(async (upload: Upload, mapping?: ColumnMapping) => {
    setBusy(true);
    setError(undefined);
    try {
      const p = await api.post<BatchParse>("/batch/parse", { filename: upload.filename, content_base64: upload.content_base64, mapping });
      setStage({ name: "preview", upload, parse: p });
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  }, []);

  const start = async (upload: Upload, mapping: ColumnMapping | undefined, includeRows?: number[]) => {
    setBusy(true);
    setError(undefined);
    try {
      // results are fetched by the polling effect below
      const job = await api.post<BatchJob>("/batch/jobs", {
        filename: upload.filename,
        content_base64: upload.content_base64,
        mapping,
        include_rows: includeRows,
      });
      live.current = job.job_id;
      setStage({ name: "job", upload, job });
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  };

  // Poll for new rows only (?since=n) until the job finishes.
  const jobId = stage.name === "job" ? stage.job.job_id : null;
  useEffect(() => {
    if (!jobId) return;
    let stop = false;
    let since = 0;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const { results: fresh, ...job } = await api.get<BatchJob>(`/batch/jobs/${jobId}?since=${since}`);
        if (stop) return;
        since += fresh.length;
        if (fresh.length) setResults((r) => [...r, ...fresh]);
        setStage((s) => (s.name === "job" && s.job.job_id === jobId ? { ...s, job } : s));
        if (job.state === "queued" || job.state === "running") timer = setTimeout(tick, POLL_MS);
        else live.current = null;
      } catch (e) {
        if (!stop) setError((e as ApiError).message);
      }
    };
    setResults([]);
    tick();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [jobId]);

  // Leaving the page mid-batch frees the server worker.
  useEffect(
    () => () => {
      if (live.current) api.del(`/batch/jobs/${live.current}`).catch(() => undefined);
    },
    [],
  );

  const cancel = async () => {
    if (!jobId) return;
    await api.del(`/batch/jobs/${jobId}`).catch(() => undefined);
    live.current = null;
    setStage((s) => (s.name === "job" ? { ...s, job: { ...s.job, state: "cancelled" } } : s));
  };

  const reset = () => {
    if (live.current) api.del(`/batch/jobs/${live.current}`).catch(() => undefined);
    live.current = null;
    setResults([]);
    setError(undefined);
    setStage({ name: "upload" });
  };

  if (limits.error) return <Panel><ErrorState message={limits.error.message} onRetry={limits.retry} /></Panel>;

  return (
    <div className="flex flex-col gap-6">
      {stage.name === "upload" && <UploadStep limits={limits.data} busy={busy} error={error} onUpload={(u) => parse(u)} />}

      {stage.name === "preview" && (
        <>
          <PreviewStep
            key={stage.upload.filename + stage.upload.size}
            filename={stage.upload.filename}
            parse={stage.parse}
            busy={busy}
            onMapping={(m) => parse(stage.upload, m)}
            onBack={reset}
            onStart={(rows) => start(stage.upload, stage.parse.mapping, rows)}
          />
          {error && <Panel><ErrorState message={error} /></Panel>}
        </>
      )}

      {stage.name === "job" && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="eyebrow">Bulk analysis · step 3</span>
            <Button size="sm" variant="ghost" onClick={reset}>
              <RotateCcw /> New batch
            </Button>
          </div>
          <Progress job={stage.job} onCancel={cancel} />
          {error && <Panel><ErrorState message={error} /></Panel>}
          {results.length > 0 && <BatchCharts results={results} />}
          <ResultsTable results={results} jobId={stage.job.job_id} done={stage.job.state === "done"} />
        </>
      )}

      {limits.data && stage.name !== "job" && (
        <PredictionNotice
          prediction={{ status: "not_available", label: "Prediction not available", reason: limits.data.prediction.reason, condition: limits.data.prediction.condition, score: null }}
        />
      )}
    </div>
  );
}
