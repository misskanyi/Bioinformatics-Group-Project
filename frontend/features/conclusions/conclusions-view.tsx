"use client";

import { BookOpen, CheckCircle2, CircleDashed, CircleSlash, ExternalLink, FlaskConical, Github, Library, Lightbulb, ListChecks } from "lucide-react";
import Link from "next/link";

import { Badge, ErrorState, Notice, Panel, PanelHeader, Skeleton } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { doiUrl, num } from "@/lib/utils";
import type { Audit, Datasets, Modelling, Overview } from "@/types/api";

const REPO = "https://github.com/misskanyi/Bioinformatics-Group-Project";

type Status = "achieved" | "partial" | "not";

const STATUS_STYLE: Record<Status, { label: string; color: string; icon: typeof CheckCircle2 }> = {
  achieved: { label: "Achieved", color: "#69E8C3", icon: CheckCircle2 },
  partial: { label: "Partially achieved", color: "#E8B56B", icon: CircleDashed },
  not: { label: "Not achieved", color: "#EF8A9A", icon: CircleSlash },
};

const METHODS = [
  [
    "Reference set",
    "PAZy PET assays were classified per assay (breakdown detected, none detected, unclear, excluded). Proteins with a valid sequence and detected PET breakdown in at least one study form the reference set; no protein in PAZy has only zero measurements, so there is no tested-inactive class.",
  ],
  [
    "Sequence matching",
    "Smith–Waterman local alignment (Biopython PairwiseAligner, BLOSUM62, gap open −11, extend −1). Hits are ranked by a length-normalised score; identity, query coverage, reference coverage and a shuffled-sequence z-score are reported. Interpretation bands follow the twilight-zone literature (Rost, 1999).",
  ],
  [
    "Clustering",
    "All-against-all alignments give an identity matrix. Hierarchical, k-means and DBSCAN variants were compared on silhouette, bootstrap stability and within-cluster identity; average-linkage hierarchical clustering was selected, and the result was tested against random-label and shuffled-distance nulls.",
  ],
  [
    "Similarity network",
    "Proteins are joined when local-alignment identity is ≥ 40% over ≥ 70% of both sequences. Thresholds can be changed in the explorer; the edge rule and a sensitivity table are exported with the network.",
  ],
  [
    "Temperatures",
    "Reported assay temperatures are shown as tested. A best tested temperature is reported only within a comparable series (same protein, paper, metric, unit, pH, duration and loading) with at least three temperatures, and is never called an optimum.",
  ],
  [
    "Supervised learning",
    "Target: PET conversion detected at 60 °C in the standardised screen of DOI 10.1021/acscatal.5c03460. Features: amino-acid composition and physicochemical descriptors. Evaluation: 20 repeats of 5-fold StratifiedGroupKFold grouped at 70% identity, against majority-class, random-score and cluster-label baselines, plus a 200-draw label-permutation test.",
  ],
  [
    "Organisms",
    "PAZy has no organism field. Organisms come only from UniProt, PlasticDB or the PlasticDB degraders list records with the identical (or precursor/mature-form) sequence. Similar sequences are never used to assign an organism.",
  ],
];

const SOURCES = [
  ["PAZy", "Plastics-Active Enzymes Database: protein sequences (CSV, FASTA) and curated polymer assays (JSON).", "https://www.pazy.eu"],
  ["PlasticDB", "Database of microorganisms and proteins reported to degrade plastics: protein FASTA and the degraders list.", "https://plasticdb.org"],
  ["UniProt", "UniProtKB records for three reference cutinases (organism and taxonomy annotations).", "https://www.uniprot.org"],
  ["ACS Catalysis 2025 supplement", "Standardised screen of a 477-sequence library: one protocol, explicit blanks and an LCC-ICCG control.", "https://doi.org/10.1021/acscatal.5c03460"],
];

const REFERENCES = [
  ["Rost, B. (1999)", "Twilight zone of protein sequence alignments.", "10.1093/protein/12.2.85"],
  ["Austin, H. P. et al. (2018)", "Characterization and engineering of a plastic-degrading aromatic polyesterase.", "10.1073/pnas.1718804115"],
  ["Tournier, V. et al. (2020)", "An engineered PET depolymerase to break down and recycle plastic bottles.", "10.1038/s41586-020-2149-4"],
  ["Erickson, E. et al. (2022)", "Sourcing thermotolerant poly(ethylene terephthalate) hydrolase scaffolds from natural diversity.", "10.1038/s41467-022-35237-x"],
];

const FUTURE = [
  {
    title: "Test the shortlisted candidates in the laboratory",
    text: "The highest-value next step is wet-lab work: express a handful of untested library sequences that are close relatives of characterised enzymes and assay them under one named condition. Every computational claim here ends at a hypothesis an experiment can settle.",
    icon: FlaskConical,
  },
  {
    title: "Add experimentally assessed sequences, especially negatives",
    text: "The binding constraint is not algorithms, it is labels. Published screens that report what did not work — with sequences and stated conditions — would do more for this problem than any change of model.",
    icon: ListChecks,
  },
  {
    title: "Strengthen homology-aware evaluation",
    text: "Group at several identity thresholds, not only 70%, and report scores per threshold. With 19 independent groups, confidence intervals belong next to every number.",
    icon: CircleDashed,
  },
  {
    title: "Broaden the protein families represented",
    text: "88% of the curated set falls in one lineage and 244 of 501 PETML entries are IsPETase derivatives. A model trained on this learns “resembles IsPETase”, not “degrades PET”. Metagenomic and structure-guided sampling would widen it.",
    icon: Library,
  },
  {
    title: "Model more conditions, explicitly",
    text: "Fit one classifier per assay condition on crystalline powder at 40 °C, where the classes are nearly balanced, and treat condition as a feature once several conditions are modelled. Report each condition separately rather than averaging them away.",
    icon: Lightbulb,
  },
  {
    title: "Richer sequence representations",
    text: "Protein-language-model embeddings and structure-aware features (predicted active-site geometry, binding-cleft shape) carry information that composition descriptors cannot. With so few independent groups, any such model still needs the same grouped evaluation and null test.",
    icon: BookOpen,
  },
];

function KeyFindings() {
  const overview = useApi<Overview>("/overview");
  const model = useApi<Modelling>("/modelling");
  const audit = useApi<Audit>("/audit");

  if (overview.error)
    return (
      <Panel>
        <ErrorState message={overview.error.message} onRetry={overview.retry} />
      </Panel>
    );
  if (!overview.data) return <Skeleton label="Loading key findings" className="h-80 rounded-[14px]" />;

  const s = overview.data.stats;
  const m = model.data;
  const a = audit.data?.available ? audit.data : undefined;
  const perm = m?.permutation_test;
  const best = m?.best_model;

  const findings = [
    {
      area: "Data preparation",
      headline: `${num(s.proteins)} curated PET-active proteins, and no usable negative class`,
      detail: `${num(s.pet_assays)} PET assay records passed classification. Every PAZy protein has at least one positive measurement, so the curated set supplies no protein-level negatives${a?.screen_labels ? `; the only defensible negatives are the ${a.screen_labels.never_positive_with_ge8_conditions} screening enzymes with no detected product across eight or more conditions` : ""}.`,
      tone: "#4CA8D8",
    },
    {
      area: "Sequence analysis",
      headline: "Verified PET hydrolases form one dominant motif-sharing lineage",
      detail: `${s.clusters} clusters emerged from alignment distances, with 263 of 298 proteins in one lineage and 296 of 298 carrying the G-x-S-x-G catalytic motif. H1 is supported.`,
      tone: "#48E1CD",
    },
    {
      area: "Clustering validity",
      headline: "The grouping is stronger than any null model tested",
      detail: "Silhouette 0.344 against at most −0.02 for random labels of the same sizes and 0.03 for average linkage on shuffled distances (200 draws each, p = 0.005). Composition features alone do not recover these families (ARI 0.08).",
      tone: "#69E8C3",
    },
    {
      area: "Conditions",
      headline: "Apparent temperature differences between groups are a sampling artefact",
      detail: "Across all PAZy assays, groups differ strongly in assay temperature (q = 0.0005). Inside the one standardised screen the same comparison is not significant after correction. H2 is not confirmed.",
      tone: "#E8B56B",
    },
    {
      area: "Machine learning",
      headline: "Sequence features do not predict detection at 60 °C",
      detail: best
        ? `Best model ROC AUC ${best.roc_auc_mean.toFixed(3)} ± ${best.roc_auc_sd.toFixed(3)} under homology-grouped cross-validation, against a 0.50 majority-class baseline${perm ? `, with a permutation-test p of ${perm.empirical_p}` : ""}. H3 is not supported.`
        : "Model outputs have not been generated.",
      tone: "#EF8A9A",
    },
    {
      area: "Candidate discovery",
      headline: "Candidates are identified by measured similarity, not by a model score",
      detail: `${m?.candidates.pool != null ? `${num(m.candidates.pool)} untested library sequences are available as a candidate pool, but ` : ""}no ranking is published, because the classifier does not clear its null. Sequence matching against characterised enzymes remains the usable shortlisting tool.`,
      tone: "#B49CF5",
    },
  ];

  return (
    <Panel>
      <PanelHeader eyebrow="Key findings" title="What the investigation established" description="Each finding names the analysis it comes from. Results that did not hold up are included." />
      <div className="stagger grid gap-3 p-5 lg:grid-cols-2">
        {findings.map((f) => (
          <div key={f.area} className="hover-card rounded-xl border border-line/70 bg-void/40 p-4">
            <div className="eyebrow" style={{ color: f.tone }}>
              {f.area}
            </div>
            <div className="mt-2 text-[15px] font-medium leading-snug">{f.headline}</div>
            <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{f.detail}</p>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function ObjectiveAssessment() {
  const model = useApi<Modelling>("/modelling");
  const m = model.data;
  const best = m?.best_model;

  const rows: { n: string; title: string; status: Status; evidence: string }[] = [
    {
      n: "O1",
      title: "Collect and clean experimentally tested PET-related sequences",
      status: "achieved",
      evidence:
        "298 curated PET-active proteins with validated sequences, every one identical to the raw PAZy record, with assay-level outcome classification and a published audit of all four sources. Positive and below-detection observations are stored separately.",
    },
    {
      n: "O2",
      title: "Analyse sequence features, motifs and similarity",
      status: "achieved",
      evidence:
        "44,253 pairwise alignments, a validated clustering solution tested against two null models, motif and domain analysis, and a sequence-similarity network exported in Cytoscape format.",
    },
    {
      n: "O3",
      title: "Develop supervised models for defined experimental conditions",
      status: "partial",
      evidence: best
        ? `Models were built and evaluated correctly — condition-specific target, homology-grouped splits, baselines and a permutation test — but none reached usable performance (best ROC AUC ${best.roc_auc_mean.toFixed(3)}). The method is in place; the result is negative.`
        : "Model outputs have not been generated.",
    },
    {
      n: "O4",
      title: "Evaluate models and identify promising untested candidates",
      status: "partial",
      evidence:
        "Evaluation was completed thoroughly and reported in full, including the negative outcome. Candidate ranking by predicted activity was deliberately not published, because the model does not beat its null; the untested candidate pool is identified and documented for future work.",
    },
  ];

  return (
    <Panel>
      <PanelHeader eyebrow="Objectives assessment" title="Did the project do what it set out to do?" description="Status is judged against evidence produced by the pipeline, not against intentions." />
      <div className="stagger flex flex-col gap-3 p-5">
        {rows.map((r) => {
          const st = STATUS_STYLE[r.status];
          const Icon = st.icon;
          return (
            <div key={r.n} className="hover-card rounded-xl border border-line/70 bg-void/40 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-md border border-teal/40 bg-teal/10 px-2 py-0.5 font-mono text-[11px] text-teal">{r.n}</span>
                <span className="font-medium">{r.title}</span>
                <span className="ml-auto">
                  <Badge color={st.color} dot={false}>
                    <Icon className="size-3" /> {st.label}
                  </Badge>
                </span>
              </div>
              <p className="mt-2 text-[13px] leading-relaxed text-muted">{r.evidence}</p>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function Answer() {
  const model = useApi<Modelling>("/modelling");
  const best = model.data?.best_model;
  return (
    <Panel glow className="overflow-hidden">
      <div className="grid-bg absolute inset-0 opacity-25" />
      <div className="relative p-6 sm:p-9">
        <div className="eyebrow text-teal">Answer to the research question</div>
        <p className="mt-3 max-w-4xl text-lg font-medium leading-snug tracking-tight sm:text-xl">
          How can protein sequence analysis and machine learning help identify promising enzyme candidates for PET plastic recycling?
        </p>
        <div className="mt-5 max-w-4xl space-y-3 text-sm leading-relaxed text-muted">
          <p>
            <b className="text-ink">Sequence analysis helps; machine learning, on this data, does not yet.</b> Alignment-based analysis reliably places an
            unknown protein among experimentally characterised PET hydrolases, recovers a motif-sharing lineage that no null model reproduces, and gives a
            defensible shortlist: proteins whose closest characterised relatives have published PET activity are worth testing first.
          </p>
          <p>
            The supervised component returns a clear negative. Trained on the only condition-comparable labels available and evaluated with homology-grouped
            cross-validation, composition and physicochemical features did not predict whether PET conversion is still detected at 60 °C
            {best ? ` (ROC AUC ${best.roc_auc_mean.toFixed(3)} against a 0.50 baseline)` : ""}, and the score falls inside a shuffled-label null. Reporting
            that model as a predictor would be wrong.
          </p>
          <p>
            The limiting factor is the data, not the algorithm. No protein-level negatives exist outside one screen; 88% of verified enzymes sit in a single
            lineage; and activity depends so strongly on substrate, temperature and pH that a condition-free claim means little. Machine learning can help with
            this question — once labelled negatives under stated conditions exist in quantity, across more protein families.
          </p>
          <p className="text-ink/80">
            So the honest answer: this project narrows the search by similarity and by family, says clearly which sequences deserve an assay, and shows exactly
            what new data a working predictor would need.
          </p>
        </div>
      </div>
    </Panel>
  );
}

function Significance() {
  return (
    <Panel>
      <PanelHeader eyebrow="Biological significance" title="Why this matters for PET recycling" />
      <div className="stagger grid gap-4 p-5 md:grid-cols-3">
        {[
          [
            "Prioritising laboratory effort",
            "Expressing and assaying one enzyme costs days of bench time. A ranked similarity report, with the published evidence for each relative attached, lets a group spend that time on sequences with the best prior odds.",
          ],
          [
            "Mapping the known family",
            "The clustering shows that verified PET hydrolases are far less diverse than the literature's enzyme names suggest, and that subgroup G1b differs mainly by accessory binding domains. Knowing where the gaps are tells discovery programmes where to look.",
          ],
          [
            "Setting the evidence bar",
            "The audit quantifies a trap that is easy to fall into: most published PET-enzyme datasets overlap each other almost completely at the sequence level. Any future model in this field needs identity-based splits, or its reported accuracy is an artefact.",
          ],
        ].map(([t, d]) => (
          <div key={t} className="hover-card rounded-xl border border-line/70 bg-void/40 p-4">
            <div className="text-[13px] font-medium">{t}</div>
            <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{d}</p>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function Limitations() {
  const res = useApi<Datasets>("/datasets");
  const model = useApi<Modelling>("/modelling");
  return (
    <Panel>
      <PanelHeader eyebrow="Limitations" title="What this work cannot support" description="Scientific and technical constraints, stated so that results are not over-read." />
      <div className="stagger grid gap-3 p-5 lg:grid-cols-2">
        {res.data?.limitations.map((l) => (
          <div key={l} className="hover-card rounded-lg border border-line/70 bg-void/40 p-3.5 text-[13px] leading-relaxed text-ink/85">
            {l}
          </div>
        ))}
        {model.data?.limitations.map((l) => (
          <div key={l.title} className="hover-card rounded-lg border border-line/70 bg-void/40 p-3.5">
            <div className="text-[13px] font-medium">{l.title}</div>
            <p className="mt-1 text-xs leading-relaxed text-muted">{l.detail}</p>
          </div>
        ))}
        {!res.data && !model.data && (res.error || model.error ? (
          <ErrorState message={(res.error ?? model.error)!.message} onRetry={res.error ? res.retry : model.retry} />
        ) : (
          <Skeleton label="Loading limitations" className="h-40" />
        ))}
      </div>
    </Panel>
  );
}

function FutureWork() {
  return (
    <Panel>
      <PanelHeader eyebrow="Recommendations" title="What to do next" description="Ordered by how much each would move the research question forward." />
      <div className="stagger grid gap-3 p-5 md:grid-cols-2">
        {FUTURE.map((f, i) => (
          <div key={f.title} className="hover-card flex gap-3 rounded-xl border border-line/70 bg-void/40 p-4">
            <div className="grid size-8 shrink-0 place-items-center rounded-lg border border-teal/30 bg-teal/10 text-teal">
              <f.icon className="size-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-[11px] text-teal/80">{String(i + 1).padStart(2, "0")}</span>
                <span className="text-[13px] font-medium">{f.title}</span>
              </div>
              <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{f.text}</p>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function Reproducibility() {
  const res = useApi<Datasets>("/datasets");
  return (
    <div className="flex flex-col gap-6">
      <Panel id="methods" className="scroll-mt-24">
        <PanelHeader eyebrow="Research documentation" title="Methods" description="How each result in this application was produced." />
        <dl className="flex flex-col gap-5 p-5">
          {METHODS.map(([t, d]) => (
            <div key={t}>
              <dt className="font-medium">{t}</dt>
              <dd className="mt-1 text-sm leading-relaxed text-muted">{d}</dd>
            </div>
          ))}
        </dl>
      </Panel>

      <div className="grid gap-6 xl:grid-cols-2">
        <Panel id="sources" className="scroll-mt-24">
          <PanelHeader eyebrow="Dataset sources" title="Where the data comes from" />
          <div className="stagger flex flex-col gap-3 p-5">
            {SOURCES.map(([n, d, u]) => (
              <div key={n} className="rounded-lg border border-line/60 bg-void/40 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
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

        <Panel id="references" className="scroll-mt-24">
          <PanelHeader eyebrow="References" title="Literature cited in the analysis" description={res.data ? `The curated assays themselves come from ${res.data.references.length} publications, listed on the data page.` : undefined} />
          <ul className="stagger flex flex-col gap-3 p-5">
            {REFERENCES.map(([who, what, doi]) => (
              <li key={doi} className="text-sm leading-relaxed">
                <span className="text-ink">{who}</span> <span className="text-muted">{what}</span>{" "}
                <a href={doiUrl(doi)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-mono text-xs text-cyan hover:underline">
                  {doi} <ExternalLink className="size-3" />
                </a>
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <Panel id="reproducibility" className="scroll-mt-24">
        <PanelHeader eyebrow="Reproducibility" title="Run it yourself" description="Every figure and table on this site is regenerated by the pipeline from the files in data/." />
        <div className="grid gap-4 p-5 lg:grid-cols-[1.2fr_1fr]">
          <pre className="overflow-x-auto rounded-lg border border-line/70 bg-void/70 p-4 font-mono text-[11px] leading-relaxed text-muted">
{`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

.venv/bin/python analyze_pet_dataset.py          # feasibility + assay labelling
.venv/bin/python -m pet_explorer.pipeline        # all analysis stages
.venv/bin/uvicorn backend.main:app --port 8000   # API over the cached outputs
cd frontend && npm run dev                       # this website
.venv/bin/python -m pytest -q tests backend/tests`}
          </pre>
          <div className="flex flex-col gap-2">
            <a href={REPO} target="_blank" rel="noreferrer" className="flex items-center gap-3 rounded-lg border border-line/70 bg-void/40 p-3 transition hover:border-teal/50">
              <Github className="size-4 text-teal" />
              <span className="min-w-0">
                <span className="block text-[13px] font-medium">GitHub repository</span>
                <span className="block truncate font-mono text-[11px] text-muted">{REPO.replace("https://", "")}</span>
              </span>
            </a>
            <div className="rounded-lg border border-line/70 bg-void/40 p-3">
              <div className="text-[13px] font-medium">Notebook</div>
              <p className="mt-1 text-xs leading-relaxed text-muted">
                <span className="font-mono">notebooks/pet_enzyme_explorer.ipynb</span> reproduces the analysis end to end with interpretation, and opens in
                Google Colab from the repository.
              </p>
            </div>
            <div className="rounded-lg border border-line/70 bg-void/40 p-3">
              <div className="text-[13px] font-medium">Processed data</div>
              <p className="mt-1 text-xs leading-relaxed text-muted">
                All derived tables are downloadable from{" "}
                <Link href="/data?section=acquisition" className="text-teal hover:underline">
                  Data Preparation
                </Link>
                , and the audit report lives in <span className="font-mono">outputs/dataset_audit/REPORT.md</span>.
              </p>
            </div>
          </div>
        </div>
      </Panel>
    </div>
  );
}

export function ConclusionsView() {
  return (
    <div className="flex flex-col gap-6">
      <Answer />
      <KeyFindings />
      <ObjectiveAssessment />
      <Significance />
      <Limitations />
      <FutureWork />
      <Reproducibility />
      <Notice>
        Claims on this page are limited to what the outputs support. Where an analysis failed to clear its null, it is reported as a negative result rather
        than softened — see <Link href="/validation" className="text-teal hover:underline">Model Validation</Link> for the full evidence.
      </Notice>
    </div>
  );
}
