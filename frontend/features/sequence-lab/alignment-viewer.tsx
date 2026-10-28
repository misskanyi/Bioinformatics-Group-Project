"use client";

import { useMemo, useState } from "react";

import { InfoTip } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";
import type { Hit } from "@/types/api";

type Kind = "match" | "sub" | "gap";

const STYLE: Record<Kind, string> = {
  match: "bg-teal/15 text-teal",
  sub: "text-amber",
  gap: "text-rose/80",
};

/**
 * Renders the local alignment returned by the backend (the same alignment the
 * identity and coverage figures were computed from).
 */
export function AlignmentViewer({ hit, queryLabel }: { hit: Hit; queryLabel: string }) {
  const [width, setWidth] = useState(60);
  const [hover, setHover] = useState<number | null>(null);

  const cols = useMemo(() => {
    const q = hit.aligned_query;
    const t = hit.aligned_target;
    let qi = hit.query_range[0];
    let ti = hit.target_range[0];
    return Array.from(q, (qc, i) => {
      const tc = t[i];
      const kind: Kind = qc === "-" || tc === "-" ? "gap" : qc === tc ? "match" : "sub";
      const col = { qc, tc, kind, qpos: qc === "-" ? null : qi, tpos: tc === "-" ? null : ti };
      if (qc !== "-") qi++;
      if (tc !== "-") ti++;
      return col;
    });
  }, [hit]);

  const counts = useMemo(
    () => cols.reduce((acc, c) => ({ ...acc, [c.kind]: acc[c.kind] + 1 }), { match: 0, sub: 0, gap: 0 } as Record<Kind, number>),
    [cols],
  );

  const blocks = [];
  for (let s = 0; s < cols.length; s += width) blocks.push(cols.slice(s, s + width));

  const h = hover != null ? cols[hover] : null;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs">
        <span className="flex items-center gap-1.5">
          <span className="rounded-sm bg-teal/15 px-1 font-mono text-teal">A</span>
          Identical <b className="tabular text-ink">{counts.match}</b>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="px-1 font-mono text-amber">A</span>
          Substitution <b className="tabular text-ink">{counts.sub}</b>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="px-1 font-mono text-rose/80">-</span>
          Gap <b className="tabular text-ink">{counts.gap}</b>
        </span>
        <span className="text-muted">{cols.length} aligned columns</span>
        <InfoTip content="Smith–Waterman local alignment (BLOSUM62, gap open −11 / extend −1). Only the aligned region is shown; residues outside it are not part of the alignment." />
        <div className="ml-auto flex items-center gap-1 rounded-md border border-line p-0.5">
          {[40, 60, 80].map((w) => (
            <button
              key={w}
              onClick={() => setWidth(w)}
              className={cn("rounded px-2 py-0.5 font-mono text-[10px]", w === width ? "bg-elevated text-teal" : "text-muted hover:text-ink")}
            >
              {w}
            </button>
          ))}
        </div>
      </div>

      <div className="h-6 font-mono text-[11px] text-muted" aria-live="polite">
        {h
          ? `Column ${hover! + 1}: query ${h.qc}${h.qpos ?? "—"} · ${hit.protein_name} ${h.tc}${h.tpos ?? "—"} · ${
              h.kind === "match" ? "identical" : h.kind === "sub" ? "substitution" : "gap"
            }`
          : "Hover a column to inspect positions"}
      </div>

      <div className="max-h-[420px] overflow-auto rounded-lg border border-line/70 bg-void/70 p-3" onMouseLeave={() => setHover(null)}>
        {blocks.map((block, b) => {
          const start = b * width;
          const qStart = block.find((c) => c.qpos != null)?.qpos ?? "";
          const tStart = block.find((c) => c.tpos != null)?.tpos ?? "";
          return (
            <div key={b} className="mb-3 font-mono text-[12px] leading-[18px] last:mb-0">
              <div className="flex whitespace-pre">
                <span className="w-24 shrink-0 truncate pr-2 text-muted">{queryLabel}</span>
                <span className="w-12 shrink-0 pr-2 text-right text-muted/70">{qStart}</span>
                {block.map((c, i) => (
                  <span
                    key={i}
                    onMouseEnter={() => setHover(start + i)}
                    className={cn("inline-block w-[1ch] text-center", STYLE[c.kind], hover === start + i && "outline outline-1 outline-ink/60")}
                  >
                    {c.qc}
                  </span>
                ))}
              </div>
              <div className="flex whitespace-pre">
                <span className="w-24 shrink-0" />
                <span className="w-12 shrink-0" />
                {block.map((c, i) => (
                  <span key={i} className="inline-block w-[1ch] text-center text-muted/70">
                    {c.kind === "match" ? "|" : c.kind === "sub" ? "·" : " "}
                  </span>
                ))}
              </div>
              <div className="flex whitespace-pre">
                <span className="w-24 shrink-0 truncate pr-2 text-muted">{hit.protein_name}</span>
                <span className="w-12 shrink-0 pr-2 text-right text-muted/70">{tStart}</span>
                {block.map((c, i) => (
                  <span
                    key={i}
                    onMouseEnter={() => setHover(start + i)}
                    className={cn("inline-block w-[1ch] text-center", STYLE[c.kind], hover === start + i && "outline outline-1 outline-ink/60")}
                  >
                    {c.tc}
                  </span>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
