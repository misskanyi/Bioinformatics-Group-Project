"use client";

import { Hourglass } from "lucide-react";

import { Badge } from "@/components/ui/primitives";
import { C, EVIDENCE } from "@/lib/palette";
import type { EvidenceStatus, PredictionBlock } from "@/types/api";

// Four kinds of statement this page can make, never mixed up:
//   experimental observation · sequence-similarity evidence · computational prediction · unknown / untested
export const EVIDENCE_STATUS: Record<EvidenceStatus, { label: string; short: string; color: string; detail: string }> = {
  experimental: {
    label: "Experimental (identical reference)",
    short: "Experimental",
    color: EVIDENCE.experimental.color,
    detail: "The sequence is identical to a characterised protein, so the published PET assays apply to it directly.",
  },
  similarity: {
    label: "Sequence similarity",
    short: "Similarity",
    color: EVIDENCE.computational.color,
    detail: "Related to a characterised PET-active protein. Similarity is evidence for follow-up, not proof of activity.",
  },
  unknown: {
    label: "Unknown / untested",
    short: "Unknown / untested",
    color: EVIDENCE.uncertain.color,
    detail: "No reliable similarity to any characterised PET-active protein and no experimental record.",
  },
};

export function EvidenceBadge({ status, short }: { status?: EvidenceStatus; short?: boolean }) {
  if (!status) return <span className="text-xs text-muted">—</span>;
  const s = EVIDENCE_STATUS[status];
  return (
    <Badge color={s.color} className="whitespace-nowrap">
      {short ? s.short : s.label}
    </Badge>
  );
}

export function PredictionBadge({ prediction, short }: { prediction?: PredictionBlock; short?: boolean }) {
  if (!prediction) return <span className="text-xs text-muted">—</span>;
  return (
    <Badge color={C.slate} dot={false} className="whitespace-nowrap">
      <Hourglass className="size-3" /> {short ? "Not available" : prediction.label}
    </Badge>
  );
}

/** States the prediction status, the reason and the only condition a model could speak to. */
export function PredictionNotice({ prediction }: { prediction: PredictionBlock }) {
  const c = prediction.condition;
  return (
    <div className="rounded-xl border border-dashed border-amber/40 bg-amber/[0.05] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="eyebrow text-amber">Computational prediction</div>
        <PredictionBadge prediction={prediction} />
      </div>
      <p className="mt-2 text-[13px] leading-relaxed text-ink/85">{prediction.reason}</p>
      <dl className="mt-3 grid gap-x-4 gap-y-1 text-xs sm:grid-cols-[auto_1fr]">
        <dt className="text-muted">Condition</dt>
        <dd className="text-ink/90">{c.target}</dd>
        <dt className="text-muted">Substrate</dt>
        <dd className="text-ink/90">{c.substrate}</dd>
        <dt className="text-muted">Protocol</dt>
        <dd className="text-ink/90">{c.protocol}</dd>
      </dl>
      <p className="mt-2 text-xs text-muted">No probability or optimum temperature is estimated: no validated activity or temperature-response model exists.</p>
    </div>
  );
}
