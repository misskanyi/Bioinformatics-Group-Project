"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/primitives";
import { AlignmentViewer } from "@/features/sequence-lab/alignment-viewer";
import { SequenceProfilePanel } from "@/features/sequence-lab/sequence-profile";
import { networkHref } from "@/lib/nav";
import { pct } from "@/lib/utils";
import type { BatchResult, SequenceProfile } from "@/types/api";

import { EVIDENCE_STATUS, EvidenceBadge, PredictionBadge } from "../evidence";
import { RESULT_STATUS } from "./status";

export function ProteinDetail({ result, onClose }: { result: BatchResult | null; onClose: () => void }) {
  const r = result;
  const top = r?.hits?.[0];
  const profile: SequenceProfile | null =
    r?.composition && r.physicochemical && r.motifs && r.length
      ? { length: r.length, composition: r.composition, physicochemical: r.physicochemical, motifs: r.motifs }
      : null;

  return (
    <Dialog.Root open={!!r} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-void/70 backdrop-blur-sm" />
        <Dialog.Content
          aria-describedby={undefined}
          className="panel fixed inset-y-0 right-0 z-50 flex w-[min(980px,100vw)] flex-col overflow-hidden rounded-none border-y-0 border-r-0 shadow-2xl"
        >
          {r && (
            <>
              <div className="flex items-start justify-between gap-4 border-b border-line/60 p-5">
                <div className="min-w-0">
                  <div className="eyebrow">
                    Record {r.row} · {r.source}
                  </div>
                  <Dialog.Title className="mt-1 break-all font-mono text-lg font-semibold">{r.protein_id}</Dialog.Title>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <Badge color={RESULT_STATUS[r.status].color}>{RESULT_STATUS[r.status].label}</Badge>
                    <EvidenceBadge status={r.evidence_status} />
                    <PredictionBadge prediction={r.prediction} />
                    {r.organism && <span className="text-xs text-muted">Organism (as supplied): {r.organism}</span>}
                  </div>
                </div>
                <Dialog.Close className="rounded-md p-1 text-muted transition hover:bg-elevated hover:text-ink" aria-label="Close">
                  <X className="size-5" />
                </Dialog.Close>
              </div>

              <div className="flex-1 space-y-5 overflow-y-auto p-5">
                {(r.errors.length > 0 || r.warnings.length > 0) && (
                  <div className="rounded-xl border border-line/70 bg-void/40 p-4 text-[13px]">
                    {r.errors.map((e) => (
                      <p key={e} className="text-rose">
                        {e}
                      </p>
                    ))}
                    {r.warnings.map((w) => (
                      <p key={w} className="text-muted">
                        {w}
                      </p>
                    ))}
                  </div>
                )}

                {r.evidence_status && (
                  <p className="text-[13px] leading-relaxed text-muted">{EVIDENCE_STATUS[r.evidence_status].detail}</p>
                )}

                {r.hits && r.hits.length > 0 && (
                  <div className="rounded-xl border border-line/70 bg-void/40 p-4">
                    <div className="eyebrow mb-3">Nearest characterised PET-active proteins</div>
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[640px] text-left text-xs">
                        <thead>
                          <tr className="text-muted">
                            <th className="py-1.5 pr-3 font-medium">Reference</th>
                            <th className="py-1.5 pr-3 font-medium">Identity</th>
                            <th className="py-1.5 pr-3 font-medium">Coverage (query / ref.)</th>
                            <th className="py-1.5 pr-3 font-medium">Shuffle z</th>
                            <th className="py-1.5 pr-3 font-medium">Interpretation</th>
                            <th className="py-1.5 font-medium">Reference evidence (experimental)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {r.hits.map((h) => (
                            <tr key={h.protein_id} className="border-t border-line/40 align-top">
                              <td className="py-2 pr-3">
                                <Link href={networkHref(h.protein_id)} className="font-mono font-semibold text-cyan hover:underline">
                                  {h.protein_name}
                                </Link>
                                <div className="text-[10px] text-muted">{h.reference.subcluster}</div>
                              </td>
                              <td className="tabular py-2 pr-3 font-mono">{pct(h.identity)}</td>
                              <td className="tabular py-2 pr-3 font-mono">
                                {pct(h.query_coverage, 0)} / {pct(h.target_coverage, 0)}
                              </td>
                              <td className="tabular py-2 pr-3 font-mono">{h.shuffled_z.toFixed(1)}</td>
                              <td className="py-2 pr-3 text-ink/85">{h.interpretation}</td>
                              <td className="py-2 text-ink/85">
                                {h.reference.n_positive_assays} positive of {h.reference.n_pet_assays} PET assays · {h.reference.n_publications} publication
                                {h.reference.n_publications === 1 ? "" : "s"}
                                {h.reference.temperatures_with_activity_c.length > 0 && (
                                  <div className="text-[10px] text-muted">activity reported at {h.reference.temperatures_with_activity_c.join(", ")} °C</div>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <p className="mt-3 text-[11px] text-muted">
                      Assay evidence belongs to the reference protein. It transfers to this sequence only as a hypothesis, more weakly the lower the identity and
                      coverage.
                    </p>
                  </div>
                )}

                {top?.aligned_query && top.aligned_target && (
                  <div className="rounded-xl border border-line/70 bg-void/40 p-4">
                    <div className="eyebrow mb-3">Local alignment with {top.protein_name}</div>
                    <AlignmentViewer
                      hit={{ ...top, aligned_query: top.aligned_query, aligned_target: top.aligned_target }}
                      queryLabel={r.protein_id}
                    />
                  </div>
                )}

                {profile && r.prediction && <SequenceProfilePanel profile={profile} prediction={r.prediction} />}
              </div>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
