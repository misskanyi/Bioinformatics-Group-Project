"use client";

import { ArrowDown, ArrowUp, ChevronsUpDown, Download, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Badge, EmptyState, InfoTip, Input, Panel, PanelHeader, Select } from "@/components/ui/primitives";
import { pct } from "@/lib/utils";
import type { BatchResult } from "@/types/api";

import { ASSESSMENT, AssessmentBadge, AssessmentDisclaimer, categoryOf, CATEGORY_ORDER, RulesExplainer } from "../assessment";
import { ProteinDetail } from "./protein-detail";
import { RESULT_STATUS } from "./status";

type SortKey = "row" | "protein_id" | "identity" | "coverage" | "motif" | "assessment";
const PAGE = 25;

const sortValue: Record<SortKey, (r: BatchResult) => string | number> = {
  row: (r) => r.row,
  protein_id: (r) => r.protein_id.toLowerCase(),
  identity: (r) => r.hits?.[0]?.identity ?? -1,
  coverage: (r) => (r.hits?.[0] ? Math.min(r.hits[0].query_coverage, r.hits[0].target_coverage) : -1),
  motif: (r) => r.motifs?.count ?? -1,
  assessment: (r) => {
    const c = categoryOf(r);
    return c ? CATEGORY_ORDER.indexOf(c) : 99;
  },
};

function SortHeader({ k, label, sort, onSort, tip }: { k: SortKey; label: string; sort: [SortKey, 1 | -1]; onSort: (k: SortKey) => void; tip?: string }) {
  const active = sort[0] === k;
  const Icon = !active ? ChevronsUpDown : sort[1] === 1 ? ArrowUp : ArrowDown;
  return (
    <th className="px-3 py-2 font-medium" aria-sort={active ? (sort[1] === 1 ? "ascending" : "descending") : "none"}>
      <span className="inline-flex items-center gap-1">
        <button onClick={() => onSort(k)} className="inline-flex items-center gap-1 transition-colors hover:text-ink">
          {label}
          <Icon className="size-3" />
        </button>
        {tip && <InfoTip content={tip} />}
      </span>
    </th>
  );
}

export function ResultsTable({
  results,
  jobId,
  done,
  category,
  onCategory,
}: {
  results: BatchResult[];
  jobId: string;
  done: boolean;
  category: string;
  onCategory: (c: string) => void;
}) {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<[SortKey, 1 | -1]>(["row", 1]);
  const [page, setPage] = useState(0);
  const [open, setOpen] = useState<BatchResult | null>(null);

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const f = results.filter(
      (r) =>
        (category === "all" || categoryOf(r) === category) &&
        (!needle || [r.protein_id, r.organism, r.hits?.[0]?.protein_name].some((s) => s?.toLowerCase().includes(needle))),
    );
    const [k, dir] = sort;
    return [...f].sort((a, b) => {
      const va = sortValue[k](a);
      const vb = sortValue[k](b);
      return (va < vb ? -1 : va > vb ? 1 : 0) * dir || a.row - b.row;
    });
  }, [results, q, category, sort]);

  const pages = Math.max(1, Math.ceil(rows.length / PAGE));
  const current = Math.min(page, pages - 1);
  const shown = rows.slice(current * PAGE, current * PAGE + PAGE);
  const onSort = (k: SortKey) => setSort(([sk, d]) => [k, sk === k ? ((-d) as 1 | -1) : 1]);

  return (
    <Panel>
      <PanelHeader
        eyebrow="Results"
        title="Per-protein evidence assessment"
        description="Each valid protein is aligned and assessed independently. Colours summarise measured sequence evidence; experimental evidence belongs to the matched reference enzyme."
        action={
          <div className="flex gap-2">
            <Button asChild size="sm" variant="secondary" aria-disabled={!done}>
              <a href={`/api/batch/jobs/${jobId}/export?format=csv`} download className={!done ? "pointer-events-none opacity-45" : undefined}>
                <Download /> Export CSV
              </a>
            </Button>
            <Button asChild size="sm" variant="ghost" aria-disabled={!done}>
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
              placeholder="Search protein or closest PET enzyme"
              aria-label="Search results"
              className="pl-9"
            />
          </div>
          <Select
            label="Filter by evidence category"
            value={category}
            onChange={(v) => {
              onCategory(v);
              setPage(0);
            }}
            options={[{ value: "all", label: "All evidence categories" }, ...CATEGORY_ORDER.map((c) => ({ value: c, label: ASSESSMENT[c].label }))]}
          />
          <span className="tabular ml-auto font-mono text-xs text-muted">
            {rows.length} of {results.length}
          </span>
        </div>

        {rows.length === 0 ? (
          <EmptyState title={results.length ? "No proteins in this evidence category" : "Waiting for the first results"}>
            {results.length ? "Choose another category or clear the search." : "Rows appear here as soon as each protein has been aligned."}
          </EmptyState>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-line/70">
            <table className="w-full min-w-[980px] text-left text-xs">
              <thead className="bg-void/40">
                <tr className="text-muted">
                  <SortHeader k="row" label="#" sort={sort} onSort={onSort} />
                  <SortHeader k="protein_id" label="Protein" sort={sort} onSort={onSort} />
                  <th className="px-3 py-2 font-medium">Closest PET Enzyme</th>
                  <SortHeader k="identity" label="Identity" sort={sort} onSort={onSort} tip="Identical residues over aligned columns (gaps included)." />
                  <SortHeader k="coverage" label="Coverage" sort={sort} onSort={onSort} tip="Aligned span as a share of the query / of the reference enzyme." />
                  <SortHeader k="motif" label="Catalytic Motif" sort={sort} onSort={onSort} tip="G-x-S-x-G catalytic-serine motif of α/β-hydrolases. Supporting context only, never proof of PET activity." />
                  <SortHeader k="assessment" label="Evidence Assessment" sort={sort} onSort={onSort} />
                </tr>
              </thead>
              <tbody>
                {shown.map((r) => {
                  const h = r.hits?.[0];
                  const a = r.assessment;
                  const cat = categoryOf(r);
                  return (
                    <tr
                      key={r.row}
                      tabIndex={0}
                      onClick={() => setOpen(r)}
                      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), setOpen(r))}
                      className="reveal cursor-pointer border-t border-line/40 align-top transition-colors duration-150 hover:bg-elevated/50 focus-visible:bg-elevated/60 focus-visible:outline-none"
                      aria-label={`Open details for ${r.protein_id}`}
                      style={cat ? { boxShadow: `inset 3px 0 0 ${ASSESSMENT[cat].color}` } : undefined}
                    >
                      <td className="px-3 py-2.5 font-mono text-muted">{r.row}</td>
                      <td className="max-w-56 px-3 py-2.5">
                        <div className="truncate font-mono font-medium text-ink">{r.protein_id}</div>
                        <div className="text-[10px] text-muted">
                          {r.length ? `${r.length} aa` : r.source}
                          {r.status === "duplicate" && (
                            <Badge color={RESULT_STATUS.duplicate.color} className="ml-1.5 py-0 text-[10px]">
                              duplicate of #{r.duplicate_of}
                            </Badge>
                          )}
                        </div>
                      </td>
                      <td className="min-w-44 px-3 py-2.5">
                        {h ? (
                          <>
                            <div className="font-mono font-medium text-cyan">{h.protein_name}</div>
                            <div className="max-w-52 text-[10px] leading-snug text-muted">{h.interpretation}</div>
                          </>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="tabular px-3 py-2.5 font-mono">{h ? pct(h.identity) : "—"}</td>
                      <td className="tabular px-3 py-2.5 font-mono">
                        {h ? (
                          <>
                            {pct(h.query_coverage, 0)} / {pct(h.target_coverage, 0)}
                            <div className="text-[10px] text-muted">query / ref.</div>
                          </>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="tabular px-3 py-2.5 font-mono">
                        {r.motifs ? (r.motifs.count ? `G-x-S-x-G ${r.motifs.count}×` : <span className="text-muted">absent</span>) : "—"}
                        {r.motifs?.variants?.length ? <div className="text-[10px] text-muted">{r.motifs.variants.join(", ")}</div> : null}
                      </td>
                      <td className="min-w-72 px-3 py-2.5">
                        <AssessmentBadge category={cat} known={a?.known_reference} short />
                        <p className="mt-1 line-clamp-2 max-w-sm text-[11px] leading-snug text-muted">
                          {a ? a.summary : r.errors[0] ?? (cat ? ASSESSMENT[cat].blurb : "Pending…")}
                        </p>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
          <span>Select a row for alignment details, published evidence, limitations and next steps.</span>
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
        <AssessmentDisclaimer />
        <RulesExplainer />
      </div>
      <ProteinDetail result={open} onClose={() => setOpen(null)} />
    </Panel>
  );
}
