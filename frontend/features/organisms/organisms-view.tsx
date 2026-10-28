"use client";

import { ExternalLink, HelpCircle, MapPin, Microscope, Search } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useDeferredValue, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Badge, EmptyState, ErrorState, Input, Panel, PanelHeader, Select, Skeleton } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { clusterColor, ORGANISM_EVIDENCE } from "@/lib/palette";
import { cn } from "@/lib/utils";
import type { OrganismCard, OrganismEvidence, Organisms } from "@/types/api";

const ALL = "__all";
const LEVELS: OrganismEvidence[] = ["exact_sequence", "contained_sequence", "pazy_curation_text", "none"];

function EvidenceBar({ data }: { data: Organisms }) {
  return (
    <Panel>
      <PanelHeader
        eyebrow="Organism evidence"
        title={`Source organism coverage of the ${data.n_proteins} reference proteins`}
        description="PAZy records no organism, so each link comes from an external record of the same sequence. Similarity alone never assigns an organism."
      />
      <div className="p-5">
        <div className="flex h-4 overflow-hidden rounded-full">
          {LEVELS.map((l) =>
            data.evidence_counts[l] ? (
              <motion.div
                key={l}
                initial={{ width: 0 }}
                animate={{ width: `${(100 * data.evidence_counts[l]) / data.n_proteins}%` }}
                transition={{ duration: 0.7 }}
                style={{ background: ORGANISM_EVIDENCE[l].color }}
                className="border-r border-void last:border-0"
                title={`${ORGANISM_EVIDENCE[l].label}: ${data.evidence_counts[l]}`}
              />
            ) : null,
          )}
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {LEVELS.map((l) => (
            <div key={l} className="rounded-lg border border-line/60 bg-void/40 p-3">
              <div className="tabular font-mono text-2xl font-semibold" style={{ color: ORGANISM_EVIDENCE[l].color }}>
                {data.evidence_counts[l]}
              </div>
              <div className="mt-1 text-xs text-muted">{ORGANISM_EVIDENCE[l].label}</div>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function Iso({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="flex gap-2 text-xs">
      <span className="w-20 shrink-0 text-muted">{label}</span>
      <span className={values.length ? "text-ink" : "text-muted/70"}>{values.length ? values.join("; ") : "Not documented"}</span>
    </div>
  );
}

function Card({ o, i }: { o: OrganismCard; i: number }) {
  const ev = ORGANISM_EVIDENCE[o.best_evidence];
  const disagree = o.proteins.some((p) => p.sources_disagree);
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 12) * 0.03 }}>
      <Panel className="flex h-full flex-col p-5 transition hover:border-violet/40">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="text-base font-semibold italic leading-snug">{o.organism}</h3>
            <div className="mt-0.5 font-mono text-[11px] text-muted">
              Genus {o.genus}
              {o.taxonomy_ids.length > 0 && " · "}
              {o.taxonomy_ids.map((t, k) => (
                <a
                  key={t}
                  href={`https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=${t}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-cyan hover:underline"
                >
                  {k > 0 && ", "}NCBI:txid{t}
                </a>
              ))}
            </div>
          </div>
          <div className="text-right">
            <div className="tabular font-mono text-2xl font-semibold text-violet">{o.n_proteins}</div>
            <div className="text-[10px] uppercase tracking-wide text-muted">protein{o.n_proteins === 1 ? "" : "s"}</div>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap gap-1.5">
          <Badge color={ev.color}>{ev.short}</Badge>
          {o.uncultured && <Badge color="#E8B56B">Uncultured / unspecified taxon</Badge>}
          {disagree && <Badge color="#E8B56B">Sources disagree</Badge>}
        </div>

        <div className="mt-4 flex flex-wrap gap-1.5">
          {o.proteins.slice(0, 12).map((p) => (
            <Link
              key={p.protein_id}
              href={`/networks?protein=${p.protein_id}`}
              className="rounded-md border border-line/70 bg-void/50 px-2 py-0.5 font-mono text-[11px] transition hover:border-teal/50 hover:text-teal"
              title={`${ORGANISM_EVIDENCE[p.evidence].label} · ${p.confidence} confidence`}
            >
              <span style={{ color: clusterColor(p.subcluster) }}>●</span> {p.protein_name}
            </Link>
          ))}
          {o.proteins.length > 12 && <span className="px-1 text-[11px] text-muted">+{o.proteins.length - 12} more</span>}
        </div>

        <div className="mt-4 flex flex-col gap-1.5 border-t border-line/50 pt-3">
          <Iso label="Environment" values={o.isolation_environment} />
          <Iso label="Sample" values={o.isolation_sample_type} />
          <Iso label="Location" values={o.isolation_location} />
        </div>
        <div className="mt-auto pt-3 text-[11px] text-muted">
          Evidence source: {o.sources.join(", ") || "—"}
          {o.accessions.length > 0 && <span className="font-mono"> · {o.accessions.slice(0, 3).join(", ")}</span>}
        </div>
      </Panel>
    </motion.div>
  );
}

export function OrganismsView() {
  const res = useApi<Organisms>("/organisms");
  const [text, setText] = useState("");
  const [level, setLevel] = useState(ALL);
  const [genus, setGenus] = useState(ALL);
  const [showUnknown, setShowUnknown] = useState(false);
  const [limit, setLimit] = useState(12);
  const q = useDeferredValue(text.trim().toLowerCase());

  const genera = useMemo(() => {
    const m = new Map<string, number>();
    res.data?.organisms.forEach((o) => m.set(o.genus, (m.get(o.genus) ?? 0) + 1));
    return [...m.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  }, [res.data]);

  const cards = useMemo(
    () =>
      (res.data?.organisms ?? []).filter(
        (o) =>
          (level === ALL || o.proteins.some((p) => p.evidence === level)) &&
          (genus === ALL || o.genus === genus) &&
          (!q ||
            o.organism.toLowerCase().includes(q) ||
            o.taxonomy_ids.some((t) => t.includes(q)) ||
            o.proteins.some((p) => p.protein_name.toLowerCase().includes(q) || String(p.protein_id) === q)),
      ),
    [res.data, level, genus, q],
  );

  const unknown = useMemo(
    () => (res.data?.unknown ?? []).filter((u) => !q || u.protein_name.toLowerCase().includes(q) || String(u.protein_id) === q),
    [res.data, q],
  );

  if (res.error)
    return (
      <Panel>
        <ErrorState message={res.error.message} onRetry={res.retry} />
      </Panel>
    );
  if (!res.data)
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-52 rounded-[14px]" />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-64 rounded-[14px]" />
          ))}
        </div>
      </div>
    );

  return (
    <div className="flex flex-col gap-6">
      <EvidenceBar data={res.data} />

      <Panel className="p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative w-full sm:w-72">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
            <Input
              value={text}
              onChange={(e) => {
                setText(e.target.value);
                setLimit(12);
              }} placeholder="Organism, protein name or ID, taxon ID" className="pl-8" aria-label="Search organisms" />
          </div>
          <Select className="w-52" label="Genus" value={genus} onChange={setGenus} options={[{ value: ALL, label: "All genera" }, ...genera.map(([g, n]) => ({ value: g, label: `${g} (${n})` }))]} />
          <Select
            className="w-64"
            label="Evidence level"
            value={level}
            onChange={setLevel}
            options={[{ value: ALL, label: "All evidence levels" }, ...LEVELS.slice(0, 3).map((l) => ({ value: l, label: ORGANISM_EVIDENCE[l].label }))]}
          />
          <span className="text-xs text-muted">
            {cards.length} organism name{cards.length === 1 ? "" : "s"}
          </span>
          <span className="ml-auto flex items-center gap-1.5 text-[11px] text-muted">
            <HelpCircle className="size-3.5" /> Higher taxonomy (family, phylum) is not in the provided files; genus is taken from the name.
          </span>
        </div>
      </Panel>

      {cards.length ? (
        <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {cards.slice(0, limit).map((o, i) => (
            <Card key={o.organism} o={o} i={i % 12} />
          ))}
          {cards.length > limit && (
            <div className="flex justify-center md:col-span-2 2xl:col-span-3">
              <Button variant="secondary" onClick={() => setLimit((l) => l + 24)}>
                Show more organisms ({cards.length - limit} remaining)
              </Button>
            </div>
          )}
        </div>
      ) : (
        <Panel>
          <EmptyState title="No documented organism matches" icon={<Microscope className="size-5" />}>
            The search may match a protein whose organism is unknown; see the list below.
          </EmptyState>
        </Panel>
      )}

      <Panel>
        <PanelHeader
          eyebrow="Unknown organism"
          title={`${res.data.evidence_counts.none} proteins without organism evidence`}
          description={res.data.context_note}
          action={
            <button disabled={!unknown.length} onClick={() => setShowUnknown((s) => !s)} className="rounded-md disabled:opacity-40 border border-line px-3 py-1.5 text-xs text-muted transition hover:border-teal/50 hover:text-ink">
              {!unknown.length ? "No matches" : showUnknown ? "Hide list" : `Show  proteins`}
            </button>
          }
        />
        {showUnknown && (
          <div className="mt-4 max-h-[460px] overflow-auto">
            <table className="w-full min-w-[640px] text-left text-xs">
              <thead className="sticky top-0 bg-surface">
                <tr className="text-muted">
                  {["Protein", "Subgroup", "Organism", "Most similar protein with a known organism (context only)"].map((h) => (
                    <th key={h} className="border-b border-line px-5 py-2 font-normal">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {unknown.map((u) => (
                  <tr key={u.protein_id} className="border-b border-line/40">
                    <td className="px-5 py-2 font-mono">
                      <Link href={`/networks?protein=${u.protein_id}`} className="hover:text-teal">
                        {u.protein_name}
                      </Link>
                    </td>
                    <td className="px-5 py-2 font-mono" style={{ color: clusterColor(u.subcluster) }}>
                      {u.subcluster}
                    </td>
                    <td className="px-5 py-2 text-amber">Unknown — insufficient evidence</td>
                    <td className={cn("px-5 py-2", u.closest_relative ? "text-muted" : "text-muted/50")}>{u.closest_relative ?? "None in the reference set"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel>
        <PanelHeader eyebrow="Evidence rules" title="How organisms are assigned" />
        <div className="grid gap-3 p-5 md:grid-cols-2 xl:grid-cols-4">
          {[
            { c: ORGANISM_EVIDENCE.exact_sequence.color, t: "Directly documented", d: "A UniProt, PlasticDB or degraders-list record has exactly the same sequence and names its organism." },
            { c: ORGANISM_EVIDENCE.contained_sequence.color, t: "Reliable database match", d: "The sequence overlaps a record as its precursor or mature form (one contains the other over ≥ 100 residues)." },
            { c: "#4CA8D8", t: "Similar protein elsewhere", d: "Shown only as context in the table above. A similar sequence from organism X does not mean the protein comes from X." },
            { c: ORGANISM_EVIDENCE.none.color, t: "Unknown", d: "No record of the same sequence. Isolation sources are never guessed: missing values read “Not documented”." },
          ].map((r) => (
            <div key={r.t} className="rounded-lg border border-line/60 bg-void/40 p-4">
              <div className="flex items-center gap-2 text-sm font-medium" style={{ color: r.c }}>
                <MapPin className="size-4" /> {r.t}
              </div>
              <p className="mt-2 text-xs leading-relaxed text-muted">{r.d}</p>
            </div>
          ))}
        </div>
        <p className="px-5 pb-5 text-[11px] text-muted">
          Taxonomy IDs link to the NCBI Taxonomy browser <ExternalLink className="inline size-3" />. Isolation details come from the PlasticDB degraders list
          records of the same sequence.
        </p>
      </Panel>
    </div>
  );
}
