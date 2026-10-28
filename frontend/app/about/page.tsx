import { BookOpen, Info, Library } from "lucide-react";
import type { Metadata } from "next";

import { Panel } from "@/components/ui/primitives";

export const metadata: Metadata = { title: "About" };

const METHODS = [
  ["Reference set", "PAZy PET assays were classified per assay (breakdown detected, none detected, unclear, excluded). Proteins with a valid sequence and detected PET breakdown in at least one study form the reference set; tested-inactive proteins are too few to model."],
  ["Sequence matching", "Smith–Waterman local alignment (Biopython PairwiseAligner, BLOSUM62, gap open −11, extend −1). Hits are ranked by a length-normalised score; identity, query coverage, reference coverage and a shuffled-sequence z-score are reported. Interpretation bands follow the twilight-zone literature (Rost, 1999)."],
  ["Clustering", "All-against-all alignments give an identity matrix. Hierarchical, k-means and DBSCAN variants were compared on silhouette, bootstrap stability and within-cluster identity; average-linkage hierarchical clustering was selected."],
  ["Similarity network", "Proteins are joined when local-alignment identity is ≥ 40% over ≥ 70% of both sequences. Thresholds can be changed in the explorer; the edge rule and a sensitivity table are exported with the network."],
  ["Temperatures", "Reported assay temperatures are shown as tested. A best tested temperature is reported only within a comparable series (same protein, paper, metric, unit, pH, duration and loading) with at least three temperatures, and is never called an optimum."],
  ["Organisms", "PAZy has no organism field. Organisms come only from UniProt, PlasticDB or the PlasticDB degraders list records with the identical (or precursor/mature-form) sequence. Similar sequences are never used to assign an organism."],
];

const SOURCES = [
  ["PAZy", "Plastics-Active Enzymes Database: protein sequences (CSV, FASTA) and curated polymer assays (JSON).", "https://www.pazy.eu"],
  ["PlasticDB", "Database of microorganisms and proteins reported to degrade plastics: protein FASTA and the degraders list.", "https://plasticdb.org"],
  ["UniProt", "UniProtKB records for three reference cutinases (organism and taxonomy annotations).", "https://www.uniprot.org"],
];

export default function About() {
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <Panel id="documentation" className="scroll-mt-24 p-6 sm:p-8">
        <div className="eyebrow flex items-center gap-2 text-teal">
          <BookOpen className="size-4" /> Research documentation
        </div>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight">Methods</h2>
        <dl className="mt-5 flex flex-col gap-5">
          {METHODS.map(([t, d]) => (
            <div key={t}>
              <dt className="font-medium">{t}</dt>
              <dd className="mt-1 text-sm leading-relaxed text-muted">{d}</dd>
            </div>
          ))}
        </dl>
      </Panel>

      <Panel id="sources" className="scroll-mt-24 p-6 sm:p-8">
        <div className="eyebrow flex items-center gap-2 text-teal">
          <Library className="size-4" /> Data sources
        </div>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight">Where the data comes from</h2>
        <div className="mt-5 flex flex-col gap-4">
          {SOURCES.map(([n, d, u]) => (
            <div key={n} className="rounded-lg border border-line/60 bg-void/40 p-4">
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium">{n}</span>
                <a href={u} target="_blank" rel="noreferrer" className="font-mono text-xs text-cyan hover:underline">
                  {u.replace("https://", "")}
                </a>
              </div>
              <p className="mt-1 text-sm text-muted">{d}</p>
            </div>
          ))}
        </div>
      </Panel>

      <Panel id="project" className="scroll-mt-24 p-6 sm:p-8">
        <div className="eyebrow flex items-center gap-2 text-teal">
          <Info className="size-4" /> About the project
        </div>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight">Decode Enzymes. Rethink Plastic.</h2>
        <div className="mt-4 space-y-3 text-sm leading-relaxed text-muted">
          <p>
            PET Enzyme Explorer is a fourth-year Computing for Bioinformatics group project on biological recycling of polyethylene terephthalate (PET). It helps a
            researcher place a new protein sequence among experimentally characterised PET-degrading enzymes and review the published evidence about them.
          </p>
          <p>
            A feasibility analysis of six public datasets found plenty of experimentally verified PET-active sequences but no usable PET-inactive ones. A binary
            activity classifier is therefore not supported, and the application deliberately offers evidence exploration rather than prediction: sequence
            matching, clustering, reported assay conditions and documented organisms.
          </p>
          <p className="text-ink/80">Sequence similarity to a PET hydrolase is not proof of PET activity. Only an experiment can show that.</p>
        </div>
      </Panel>
    </div>
  );
}
