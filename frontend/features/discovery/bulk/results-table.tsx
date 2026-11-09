"use client";

import { ArrowDown, ArrowUp, ChevronsUpDown, Download, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Badge, EmptyState, InfoTip, Input, Panel, PanelHeader, Select } from "@/components/ui/primitives";
import { pct } from "@/lib/utils";
import type { BatchResult } from "@/types/api";

import { EVIDENCE_STATUS, EvidenceBadge, PredictionBadge } from "../evidence";
import { ProteinDetail } from "./protein-detail";
import { RESULT_STATUS } from "./status";

type SortKey = "row" | "protein_id" | "length" | "motif" | "identity" | "status";
const PAGE = 25;

const sortValue: Record<SortKey, (r: BatchResult) => string | number> = {
  row: (r) => r.row,
  protein_id: (r) => r.protein_id.toLowerCase(),
  length: (r) => r.length ?? -1,
  motif: (r) => r.motifs?.count ?? -1,
  identity: (r) => r.hits?.[0]?.identity ?? -1,
  status: (r) => r.status,
};

function SortHeader({ k, label, sort, onSort }: { k: SortKey; label: string; sort: [SortKey, 1 | -1]; onSort: (k: SortKey) => void }) {
  const active = sort[0] === k;
  const Icon = !active ? ChevronsUpDown : sort[1] === 1 ? ArrowUp : ArrowDown;
  return (
    <th className="px-3 py-2 font-medium" aria-sort={active ? (sort[1] === 1 ? "ascending" : "descending") : "none"}>
      <button onClick={() => onSort(k)} className="inline-flex items-center gap-1 transition-colors hover:text-ink">
        {label}
        <Icon className="size-3" />
      </button>
    </th>
  );
}

export function ResultsTable({ results, jobId, done }: { results: BatchResult[]; jobId: string; done: boolean }) {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("all");
  const [evidence, setEvidence] = useState("all");
  const [sort, setSort] = useState<[SortKey, 1 | -1]>(["row", 1]);
  const [page, setPage] = useState(0);
  const [open, setOpen] = useState<BatchResult | null>(null);

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const f = results.filter(
      (r) =>
        (status === "all" || r.status === status) &&
        (evidence === "all" || r.evidence_status === evidence) &&
        (!needle || [r.protein_id, r.organism, r.hits?.[0]?.protein_name].some((s) => s?.toLowerCase().includes(needle))),
    );
    const [k, dir] = sort;
    return [...f].sort((a, b) => {
      const va = sortValue[k](a);
      const vb = sortValue[k](b);
      return (va < vb ? -1 : va > vb ? 1 : 0) * dir || a.row - b.row;
    });
  }, [results, q, status, evidence, sort]);

  const pages = Math.max(1, Math.ceil(rows.length / PAGE));
  const current = Math.min(page, pages - 1);
  const shown = rows.slice(current * PAGE, current * PAGE + PAGE);
  const onSort = (k: SortKey) => setSort(([sk, d]) => [k, sk === k ? ((-d) as 1 | -1) : 1]);
  const condition = results.find((r) => r.prediction)?.prediction?.condition;

  return (
    <Panel>
      <PanelHeader
        eyebrow="Results"
        title="Per-protein analysis"
        description="Similarity is measured; experimental evidence belongs to the matched reference; predictions are shown only when a validated model exists."
        action={
          <div className="flex gap-2">
            <Button asChild size="sm" variant="secondary" aria-disabled={!done}>
              <a href={`/api/batch/jobs/${jobId}/export?format=csv`} download className={!done ? "pointer-events-none opacity-45" : undefined}>
                <Download /> CSV
              </a>
            </Button>
            <Button asChild size="sm" variant="secondary" aria-disabled={!done}>
              <a href={`/api/batch/jobs/${jobId}/export?format=xlsx`} download className={!done ? "pointer-events-none opacity-45" : undefined}>
                <Download /> Excel
              </a>
            </Button>
          </div>
        }
      />
      <div className="flex flex-col gap-4 p-5">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-56 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
            <Input
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(0);
              }}
              placeholder="Search protein ID, organism or nearest enzyme"
              aria-label="Search results"
              className="pl-9"
            />
          </div>
          <Select
            label="Filter by status"
            value={status}
            onChange={(v) => {
              setStatus(v);
              setPage(0);
            }}
            options={[{ value: "all", label: "All statuses" }, ...Object.entries(RESULT_STATUS).map(([value, s]) => ({ value, label: s.label }))]}
          />
          <Select
            label="Filter by evidence"
            value={evidence}
            onChange={(v) => {
              setEvidence(v);
              setPage(0);
            }}
            options={[{ value: "all", label: "All evidence" }, ...Object.entries(EVIDENCE_STATUS).map(([value, s]) => ({ value, label: s.label }))]}
          />
          <span className="tabular ml-auto font-mono text-xs text-muted">
            {rows.length} of {results.length}
          </span>
        </div>

        {rows.length === 0 ? (
          <EmptyState title={results.length ? "No records match these filters" : "Waiting for the first results"} />
        ) : (
          <div className="overflow-x-auto rounded-xl border border-line/70">
            <table className="w-full min-w-[1260px] text-left text-xs">
              <thead className="bg-void/40">
                <tr className="text-muted">
                  <SortHeader k="row" label="#" sort={sort} onSort={onSort} />
                  <SortHeader k="protein_id" label="Protein ID" sort={sort} onSort={onSort} />
                  <th className="px-3 py-2 font-medium">Organism</th>
                  <SortHeader k="length" label="Length" sort={sort} onSort={onSort} />
                  <SortHeader k="motif" label="G-x-S-x-G" sort={sort} onSort={onSort} />
                  <th className="px-3 py-2 font-medium">Nearest known enzyme</th>
                  <SortHeader k="identity" label="Identity · coverage" sort={sort} onSort={onSort} />
                  <th className="px-3 py-2 font-medium">Evidence</th>
                  <th className="px-3 py-2 font-medium">Activity prediction</th>
                  <th className="px-3 py-2 font-medium">
                    <span className="inline-flex items-center gap-1">
                      Score <InfoTip content="Model score or calibrated probability. Empty because no validated model exists; no placeholder is shown." />
                    </span>
                  </th>
                  <th className="px-3 py-2 font-medium">Prediction conditions</th>
                  <SortHeader k="status" label="Status" sort={sort} onSort={onSort} />
                </tr>
              </thead>
              <tbody>
                {shown.map((r) => {
                  const h = r.hits?.[0];
                  return (
                    <tr
                      key={r.row}
                      tabIndex={0}
                      onClick={() => setOpen(r)}
                      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), setOpen(r))}
                      className="reveal cursor-pointer border-t border-line/40 align-top transition-colors duration-150 hover:bg-elevated/50 focus-visible:bg-elevated/60 focus-visible:outline-none"
                      aria-label={`Open details for ${r.protein_id}`}
                    >
                      <td className="px-3 py-2 font-mono text-muted">{r.row}</td>
                      <td className="max-w-52 truncate px-3 py-2 font-mono font-medium text-ink">{r.protein_id}</td>
                      <td className="max-w-40 truncate px-3 py-2 text-ink/80">{r.organism ?? "—"}</td>
                      <td className="tabular px-3 py-2 font-mono">{r.length ?? "—"}</td>
                      <td className="tabular px-3 py-2 font-mono">{r.motifs ? (r.motifs.count ? `${r.motifs.count}×` : "absent") : "—"}</td>
                      <td className="min-w-60 px-3 py-2">
                        {h ? (
                          <>
                            <div className="font-mono font-medium text-cyan">{h.protein_name}</div>
                            <div className="max-w-56 text-[10px] leading-snug text-muted">{h.interpretation}</div>
                          </>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="tabular px-3 py-2 font-mono">
                        {h ? (
                          <>
                            {pct(h.identity)}
                            <div className="text-[10px] text-muted">
                              {pct(h.query_coverage, 0)} / {pct(h.target_coverage, 0)}
                            </div>
                          </>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <EvidenceBadge status={r.evidence_status} short />
                      </td>
                      <td className="px-3 py-2">
                        <PredictionBadge prediction={r.prediction} short />
                      </td>
                      <td className="px-3 py-2 font-mono text-muted">—</td>
                      <td className="min-w-36 px-3 py-2 text-[11px] leading-snug text-muted">
                        {r.prediction ? `${r.prediction.condition.temperature_c} °C · ${r.prediction.condition.substrate}` : "—"}
                      </td>
                      <td className="px-3 py-2">
                        <Badge color={RESULT_STATUS[r.status].color} className="whitespace-nowrap">
                          {RESULT_STATUS[r.status].label}
                        </Badge>
                        {r.errors[0] && <div className="mt-1 max-w-48 text-[10px] leading-snug text-rose">{r.errors[0]}</div>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
          <span>
            {condition ? `Predictions would refer to: ${condition.target}, ${condition.substrate}, ${condition.protocol}.` : ""} Select a row for full details.
          </span>
          {pages > 1 && (
            <div className="flex items-center gap-2">
              <Button size="sm" variant="ghost" disabled={current === 0} onClick={() => setPage(current - 1)}>
                Previous
              </Button>
              <span className="tabular font-mono">
                {current + 1} / {pages}
              </span>
              <Button size="sm" variant="ghost" disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>
                Next
              </Button>
            </div>
          )}
        </div>
      </div>
      <ProteinDetail result={open} onClose={() => setOpen(null)} />
    </Panel>
  );
}
