"use client";

import { ExternalLink, Share2 } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Badge, Notice } from "@/components/ui/primitives";
import { clusterColor, EVIDENCE, ORGANISM_EVIDENCE } from "@/lib/palette";
import { doiUrl, pct } from "@/lib/utils";
import type { Hit, MatchMethod } from "@/types/api";

import { AlignmentViewer } from "./alignment-viewer";
import { bandColor } from "./hit-list";

function Section({ title, color, children }: { title: string; color?: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-line/60 pt-4">
      <h4 className="eyebrow mb-3 flex items-center gap-2">
        {color && <span className="size-1.5 rounded-full" style={{ background: color }} />}
        {title}
      </h4>
      {children}
    </section>
  );
}

function TempChips({ temps, active, inactive }: { temps: number[]; active: number[]; inactive: number[] }) {
  if (!temps.length) return <p className="text-sm text-amber">No assay temperature recorded.</p>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {temps.map((t) => {
        const a = active.includes(t);
        const n = inactive.includes(t);
        const color = a ? "#69E8C3" : n ? "#EF8A9A" : "#9BB3C6";
        return (
          <span
            key={t}
            title={a ? "PET breakdown detected at this temperature" : n ? "Tested; no breakdown detected by the reported method" : "Tested; outcome unclear"}
            className="tabular rounded-md border px-2 py-0.5 font-mono text-xs"
            style={{ color, borderColor: `${color}55`, background: `${color}10` }}
          >
            {t} °C
          </span>
        );
      })}
    </div>
  );
}

export function HitDetail({ hit, method, queryLabel }: { hit: Hit; method: MatchMethod; queryLabel: string }) {
  const r = hit.reference;
  const bc = bandColor(hit.interpretation, method);
  const org = ORGANISM_EVIDENCE[r.organism_evidence];
  const known = r.organism_evidence !== "none";

  return (
    <div className="flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="eyebrow">Selected reference · rank {hit.rank}</div>
          <h3 className="mt-1 font-mono text-2xl font-semibold tracking-tight">{r.protein_name}</h3>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
            <span>PAZy ID {r.protein_id}</span>·<span>{r.sequence_length} aa</span>·
            <span style={{ color: clusterColor(r.subcluster) }}>Subgroup {r.subcluster}</span>
          </div>
        </div>
        <Button asChild size="sm" variant="outline">
          <Link href={`/networks?protein=${r.protein_id}`}>
            <Share2 /> View in network
          </Link>
        </Button>
      </div>

      <div className="flex flex-wrap gap-2">
        <Badge color={EVIDENCE.experimental.color}>Experimentally verified PET activity (reference)</Badge>
        <Badge color={EVIDENCE.computational.color}>Computational similarity to your query</Badge>
        <Badge color={known ? EVIDENCE.organism.color : EVIDENCE.uncertain.color}>{known ? "Documented organism" : "Organism unknown"}</Badge>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { l: "Identity", v: pct(hit.identity), c: bc },
          { l: "Query coverage", v: pct(hit.query_coverage), c: "#4CA8D8" },
          { l: "Ref coverage", v: pct(hit.target_coverage), c: "#69E8C3" },
          { l: "Shuffle z-score", v: hit.shuffled_z.toFixed(1), c: "#B49CF5" },
        ].map((m) => (
          <div key={m.l} className="rounded-lg border border-line/70 bg-void/40 p-3">
            <div className="eyebrow text-[10px]">{m.l}</div>
            <div className="tabular mt-1 font-mono text-xl font-semibold" style={{ color: m.c }}>
              {m.v}
            </div>
          </div>
        ))}
      </div>

      <Notice>
        <b style={{ color: bc }}>{hit.interpretation}.</b> Query residues {hit.query_range[0]}–{hit.query_range[1]} align with reference residues{" "}
        {hit.target_range[0]}–{hit.target_range[1]}. Identity describes sequence similarity only; it is not a probability that your protein
        degrades PET.
      </Notice>

      <Section title="Alignment" color={EVIDENCE.computational.color}>
        <AlignmentViewer hit={hit} queryLabel={queryLabel} />
      </Section>

      <Section title="Experimental PET degradation evidence (reference protein)" color={EVIDENCE.experimental.color}>
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <div className="text-xs text-muted">Evidence label</div>
            <div className="mt-0.5 text-sm font-medium text-mint">{r.pet_label}</div>
            <div className="text-xs text-muted">{r.label_confidence} confidence</div>
          </div>
          <div>
            <div className="text-xs text-muted">PET assays</div>
            <div className="tabular mt-0.5 text-sm">
              <span className="text-mint">{r.n_positive_assays} detected</span> · <span className="text-rose">{r.n_negative_assays} not detected</span>
            </div>
            <div className="text-xs text-muted">of {r.n_pet_assays} reported assays</div>
          </div>
          <div>
            <div className="text-xs text-muted">Substrate forms</div>
            <div className="mt-0.5 text-sm">{r.substrate_forms.slice(0, 5).join(", ") || "—"}</div>
          </div>
        </div>
      </Section>

      <Section title="Reported experimental temperatures" color={EVIDENCE.experimental.color}>
        <TempChips temps={r.temperatures_tested_c} active={r.temperatures_with_activity_c} inactive={r.temperatures_without_detected_activity_c} />
        <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-muted">
          <span>
            <span className="text-mint">■</span> breakdown detected
          </span>
          <span>
            <span className="text-rose">■</span> none detected by the reported method
          </span>
          {r.ph_range && <span>pH tested: {r.ph_range}</span>}
        </div>
        {r.temperature_optimum_status && <p className="mt-2 text-xs leading-relaxed text-muted">{r.temperature_optimum_status}</p>}
      </Section>

      <Section title="Associated organism (reference protein)" color={known ? EVIDENCE.organism.color : EVIDENCE.uncertain.color}>
        {known ? (
          <div>
            <div className="text-base font-medium italic">{r.organism}</div>
            <div className="mt-1 text-xs" style={{ color: org.color }}>
              {r.organism_association ?? org.label}
              {r.organism_confidence && ` · ${r.organism_confidence} confidence`}
            </div>
            {r.organism_sources_disagree && <p className="mt-1 text-xs text-amber">Database records name more than one organism for this sequence.</p>}
            <p className="mt-2 text-xs text-muted">
              This is the organism of the matched reference protein. It does not establish the source of your query sequence.
            </p>
          </div>
        ) : (
          <p className="text-sm text-amber">Unknown — no database record with this sequence names an organism.</p>
        )}
      </Section>

      <Section title={`Supporting publications (${r.dois.length})`}>
        <ul className="flex flex-col gap-1.5">
          {r.dois.map((d) => (
            <li key={d}>
              <a href={doiUrl(d)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 font-mono text-xs text-cyan hover:text-teal hover:underline">
                {d} <ExternalLink className="size-3" />
              </a>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}
