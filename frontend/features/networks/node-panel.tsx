"use client";

import { Dna, MousePointerClick, X } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Badge, EmptyState, ErrorState, Skeleton } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { clusterColor, ORGANISM_EVIDENCE } from "@/lib/palette";
import { fmtTemps, pct } from "@/lib/utils";
import type { NetworkNode, ProteinDetail } from "@/types/api";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line/50 py-2 text-sm last:border-0">
      <span className="shrink-0 text-muted">{label}</span>
      <span className="min-w-0 text-right">{children}</span>
    </div>
  );
}

export function NodePanel({ node, onClose, onSelect }: { node: NetworkNode | null; onClose: () => void; onSelect: (id: number) => void }) {
  const detail = useApi<ProteinDetail>(node ? `/proteins/${node.id}` : null);
  if (!node)
    return (
      <EmptyState title="Select a protein" icon={<MousePointerClick className="size-5" />}>
        Click a node, or search by name or ID, to see its cluster, connections, organism and reported temperatures.
      </EmptyState>
    );
  const d = detail.data;
  const ev = ORGANISM_EVIDENCE[node.organism_evidence ?? "none"];
  return (
    <div className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="eyebrow">Protein · ID {node.id}</div>
          <h3 className="mt-1 truncate font-mono text-xl font-semibold">{node.name}</h3>
        </div>
        <button onClick={onClose} className="text-muted hover:text-ink" aria-label="Clear selection">
          <X className="size-4" />
        </button>
      </div>
      <div className="mt-3">
        <Row label="Cluster">
          <span className="font-mono" style={{ color: clusterColor(node.subcluster) }}>
            {node.cluster} · subgroup {node.subcluster}
          </span>
        </Row>
        <Row label="Sequence length">{node.length} aa</Row>
        <Row label="Connections">
          <span className="font-mono text-teal">{node.degree}</span> <span className="text-xs text-muted">at current threshold</span>
        </Row>
        <Row label="Known organism">
          {node.organism_evidence && node.organism_evidence !== "none" ? (
            <span>
              <span className="italic">{node.organism}</span>
              <br />
              <span className="text-[11px]" style={{ color: ev.color }}>
                {ev.short}
              </span>
            </span>
          ) : (
            <span className="text-amber">Unknown — insufficient evidence</span>
          )}
        </Row>
        <Row label="Temperatures tested">
          {d ? <span className="font-mono text-xs">{fmtTemps(d.temperatures_tested_c)}</span> : <Skeleton className="ml-auto h-4 w-28" />}
        </Row>
        <Row label="PET breakdown at">
          {d ? <span className="font-mono text-xs text-mint">{fmtTemps(d.temperatures_with_activity_c)}</span> : <Skeleton className="ml-auto h-4 w-20" />}
        </Row>
      </div>

      {detail.error && <ErrorState message={detail.error.message} onRetry={detail.retry} />}

      {d && (
        <>
          <div className="mt-4 flex flex-wrap gap-2">
            <Badge color="#69E8C3">{d.pet_label}</Badge>
            <Badge color="#9BB3C6" dot={false}>
              {d.n_pet_assays} assays · {d.n_publications} paper{d.n_publications === 1 ? "" : "s"}
            </Badge>
          </div>
          <div className="mt-5">
            <div className="eyebrow mb-2">Most similar proteins</div>
            <div className="flex flex-col gap-1">
              {d.nearest_references.map((n) => (
                <button
                  key={n.protein_id}
                  onClick={() => onSelect(n.protein_id)}
                  className="flex items-center justify-between rounded-md px-2 py-1.5 text-left text-xs transition hover:bg-elevated"
                >
                  <span className="font-mono">{n.protein_name}</span>
                  <span className="tabular font-mono text-muted">
                    {pct(n.identity, 0)} id · {pct(n.min_coverage, 0)} cov
                  </span>
                </button>
              ))}
            </div>
          </div>
        </>
      )}
      <Button asChild variant="primary" size="sm" className="mt-5 w-full">
        <Link href={`/sequence-lab?protein=${node.id}`}>
          <Dna /> Analyse in Sequence Laboratory
        </Link>
      </Button>
    </div>
  );
}
