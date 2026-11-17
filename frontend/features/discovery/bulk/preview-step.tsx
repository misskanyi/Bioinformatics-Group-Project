"use client";

import { ArrowLeft, Play } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Badge, Metric, Notice, Panel, PanelHeader, Select } from "@/components/ui/primitives";
import { C } from "@/lib/palette";
import { cn } from "@/lib/utils";
import type { BatchParse, ColumnMapping } from "@/types/api";

import { RECORD_STATUS } from "./status";

const FIELDS: { key: keyof ColumnMapping; label: string; required?: boolean }[] = [
  { key: "sequence", label: "Amino-acid sequence", required: true },
  { key: "protein_id", label: "Protein ID" },
  { key: "organism", label: "Organism" },
];

export function PreviewStep({
  filename,
  parse,
  busy,
  onMapping,
  onBack,
  onStart,
}: {
  filename: string;
  parse: BatchParse;
  busy: boolean;
  onMapping: (m: ColumnMapping) => void;
  onBack: () => void;
  onStart: (includeRows?: number[]) => void;
}) {
  const pdf = parse.requires_confirmation;
  const [picked, setPicked] = useState<Set<number>>(() => new Set(parse.records.filter((r) => r.status !== "invalid").map((r) => r.row)));
  const [showAll, setShowAll] = useState(false);
  const rows = showAll ? parse.records : parse.records.slice(0, 50);
  const selectedValid = useMemo(
    () => parse.records.filter((r) => r.status === "valid" && (!pdf || picked.has(r.row))).length,
    [parse.records, picked, pdf],
  );

  const toggle = (row: number) =>
    setPicked((s) => {
      const n = new Set(s);
      if (n.has(row)) n.delete(row);
      else n.add(row);
      return n;
    });

  return (
    <Panel>
      <PanelHeader
        eyebrow="Bulk analysis · step 2"
        title={`Check how ${filename} was read`}
        description="Every record is validated on its own. Invalid rows are reported and skipped; they never stop the rest of the batch."
        action={
          <Button size="sm" variant="ghost" onClick={onBack}>
            <ArrowLeft /> Choose another file
          </Button>
        }
      />
      <div className="flex flex-col gap-5 p-5">
        {parse.columns && parse.mapping && (
          <div className="rounded-xl border border-line/70 bg-void/40 p-4">
            <div className="eyebrow mb-3">Column mapping</div>
            <div className="grid gap-3 sm:grid-cols-3">
              {FIELDS.map((f) => (
                <label key={f.key} className="flex flex-col gap-1.5 text-xs text-muted">
                  {f.label}
                  {f.required && " *"}
                  <Select
                    label={f.label}
                    value={parse.mapping?.[f.key] ?? ""}
                    onChange={(v) => onMapping({ ...parse.mapping!, [f.key]: v || null })}
                    options={[...(f.required ? [] : [{ value: "", label: "— none —" }]), ...parse.columns!.map((c) => ({ value: c, label: c }))]}
                  />
                </label>
              ))}
            </div>
            {parse.preview_rows && parse.preview_rows.length > 0 && (
              <div className="mt-4 overflow-x-auto rounded-lg border border-line/60">
                <table className="w-full min-w-[520px] text-left text-[11px]">
                  <thead>
                    <tr className="text-muted">
                      {parse.columns.map((c) => (
                        <th key={c} className={cn("px-2.5 py-1.5 font-medium", Object.values(parse.mapping!).includes(c) && "text-cyan")}>
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {parse.preview_rows.map((r, i) => (
                      <tr key={i} className="border-t border-line/40">
                        {parse.columns!.map((c) => (
                          <td key={c} className="max-w-48 truncate px-2.5 py-1.5 font-mono text-ink/80">
                            {r[c]}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {pdf && (
          <Notice tone="warn">
            Sequences were extracted from the PDF text layer. Line breaks inside table cells can merge or split sequences, so check each candidate and untick
            any that look wrong before analysing.
          </Notice>
        )}

        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Metric label="Records found" value={parse.counts.total} />
          <Metric label="Valid" value={parse.counts.valid} accent={C.mint} />
          <Metric label="Invalid" value={parse.counts.invalid} accent={C.rose} />
          <Metric label="Duplicates" value={parse.counts.duplicate} accent={C.amber} hint="analysed once, results copied" />
        </div>

        <div className="overflow-x-auto rounded-xl border border-line/70">
          <table className="w-full min-w-[720px] text-left text-xs">
            <thead className="bg-void/40">
              <tr className="text-muted">
                {pdf && <th className="w-10 px-3 py-2 font-medium">Use</th>}
                <th className="px-3 py-2 font-medium">#</th>
                <th className="px-3 py-2 font-medium">Source</th>
                <th className="px-3 py-2 font-medium">Protein ID</th>
                <th className="px-3 py-2 font-medium">Organism</th>
                <th className="px-3 py-2 font-medium">Length</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Notes</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.row} className="border-t border-line/40 align-top transition-colors duration-150 hover:bg-elevated/40">
                  {pdf && (
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        aria-label={`Use record ${r.row}`}
                        checked={picked.has(r.row)}
                        onChange={() => toggle(r.row)}
                        className="size-4 accent-[var(--color-electric)]"
                      />
                    </td>
                  )}
                  <td className="px-3 py-2 font-mono text-muted">{r.row}</td>
                  <td className="px-3 py-2 font-mono text-muted">{r.source}</td>
                  <td className="max-w-56 truncate px-3 py-2 font-mono text-ink">{r.protein_id}</td>
                  <td className="max-w-44 truncate px-3 py-2 text-ink/80">{r.organism ?? "—"}</td>
                  <td className="tabular px-3 py-2 font-mono">{r.length ?? "—"}</td>
                  <td className="px-3 py-2">
                    <Badge color={RECORD_STATUS[r.status].color}>{RECORD_STATUS[r.status].label}</Badge>
                  </td>
                  <td className="px-3 py-2 text-[11px] leading-relaxed">
                    {r.errors.map((e) => (
                      <div key={e} className="text-rose">
                        {e}
                      </div>
                    ))}
                    {r.duplicate_of && <div className="text-amber">Same sequence as record {r.duplicate_of}.</div>}
                    {r.warnings.map((w) => (
                      <div key={w} className="text-muted">
                        {w}
                      </div>
                    ))}
                    {pdf && <div className="mt-0.5 break-all font-mono text-[10px] text-muted/80">{r.preview}…</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {parse.records.length > rows.length && (
          <button className="self-start text-xs text-cyan hover:underline" onClick={() => setShowAll(true)}>
            Show all {parse.records.length} records
          </button>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line/60 pt-4">
          <p className="text-xs text-muted">
            {selectedValid} valid sequence{selectedValid === 1 ? "" : "s"} will be aligned against the 298 characterised PET-active proteins and profiled.
          </p>
          <Button variant="primary" disabled={busy || !selectedValid} onClick={() => onStart(pdf ? [...picked] : undefined)}>
            <Play /> {pdf ? "Confirm and analyse" : "Analyse batch"}
          </Button>
        </div>
      </div>
    </Panel>
  );
}
