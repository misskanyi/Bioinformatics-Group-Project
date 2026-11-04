"use client";

import {
  ArrowRight,
  Binary,
  Boxes,
  Database,
  FlaskConical,
  HelpCircle,
  Library,
  ListChecks,
  Microscope,
  Ruler,
  Sparkles,
  Workflow as WorkflowIcon,
} from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { CountUp } from "@/components/ui/count-up";
import { Badge, ErrorState, InfoTip, Notice, Panel, PanelHeader, Skeleton } from "@/components/ui/primitives";
import { AA_LEGEND, HelixCanvas } from "@/components/viz/helix-canvas";
import { useApi } from "@/lib/api";
import { num } from "@/lib/utils";
import type { Audit, Example, Modelling, Overview } from "@/types/api";

const fade = (i: number) => ({
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  transition: { delay: 0.05 * i, duration: 0.4, ease: [0.22, 1, 0.36, 1] as const },
});

const RESEARCH_QUESTION =
  "How can protein sequence analysis and machine learning help identify promising enzyme candidates for PET plastic recycling?";

const OBJECTIVES = [
  {
    n: "O1",
    title: "Collect and clean experimentally tested PET-related sequences",
    text: "Assemble protein sequences with published PET assay evidence, keeping positive results and below-detection observations apart, and record the provenance of every record.",
  },
  {
    n: "O2",
    title: "Analyse sequence features, motifs and similarity",
    text: "Compare sequences by local alignment, group them, and test which composition, physicochemical and motif features track with reported PET activity.",
  },
  {
    n: "O3",
    title: "Develop supervised models for defined experimental conditions",
    text: "Train classifiers on labels that name their assay condition, using homology-aware splits so near-identical sequences cannot appear on both sides of a split.",
  },
  {
    n: "O4",
    title: "Evaluate the models and identify candidates worth testing",
    text: "Benchmark every model against baselines and a shuffled-label null, and only rank untested sequences if the evaluation supports it.",
  },
];

const HYPOTHESES = [
  {
    id: "H1",
    text: "Experimentally verified PET-hydrolysing enzymes share a common catalytic-motif lineage, so most of them fall into one sequence group rather than being spread evenly across unrelated families.",
    testedBy: "Clustering against random-label and shuffled-distance nulls",
  },
  {
    id: "H2",
    text: "Sequence groups differ in the temperatures at which PET breakdown is still detected.",
    testedBy: "Non-parametric group tests with Benjamini–Hochberg correction, inside one standardised screen",
  },
  {
    id: "H3",
    text: "Sequence-derived features (amino-acid composition, length, isoelectric point, hydropathy, instability index, secondary-structure propensity) carry enough signal to predict whether PET conversion is still detected at 60 °C under one standardised protocol, better than majority-class and shuffled-label baselines.",
    testedBy: "Grouped cross-validation (70% identity) plus a 200-draw label-permutation test",
  },
];

const METHODOLOGY = [
  { n: "01", title: "Data acquisition", icon: Database, text: "PAZy, PlasticDB, UniProt and the PETML study workbooks." },
  { n: "02", title: "Data cleaning", icon: ListChecks, text: "Assay-level labelling, sequence validation, duplicate and redundancy checks." },
  { n: "03", title: "Sequence analysis", icon: Ruler, text: "All-against-all Smith–Waterman alignment, motifs, clustering." },
  { n: "04", title: "Feature engineering", icon: Binary, text: "Composition and physicochemical descriptors per sequence." },
  { n: "05", title: "Machine learning", icon: Boxes, text: "Condition-specific classifiers on a standardised screen." },
  { n: "06", title: "Model validation", icon: Microscope, text: "Homology-grouped cross-validation against baselines and a null." },
  { n: "07", title: "Candidate discovery", icon: FlaskConical, text: "Ranking untested sequences — only where validation supports it." },
];

const SOURCES = [
  {
    name: "PAZy",
    role: "Plastics-Active Enzymes Database. Curated protein sequences and per-publication polymer assays; the source of every experimentally verified PET-active protein in this project.",
    url: "https://www.pazy.eu",
    evidence: "Experimentally validated",
    color: "#69E8C3",
  },
  {
    name: "PlasticDB",
    role: "Proteins and microorganisms reported to degrade plastics. Used for source-organism evidence and cross-checking, never as proof of activity, because entries are name-annotated rather than assay-verified.",
    url: "https://plasticdb.org",
    evidence: "Annotated",
    color: "#4CA8D8",
  },
  {
    name: "UniProt",
    role: "Reviewed records for reference cutinases, used for organism and taxonomy annotation of identical sequences.",
    url: "https://www.uniprot.org",
    evidence: "Annotated",
    color: "#B49CF5",
  },
  {
    name: "PETML",
    role: "Thirty-three digitised study workbooks of engineered PET-hydrolase variants with per-study activity and melting temperatures. Treated as within-study ordinal series — the workbooks record no units, so values are never pooled.",
    url: null,
    evidence: "Not unit-comparable",
    color: "#E8B56B",
  },
];

function Hero() {
  const examples = useApi<Example[]>("/sequence/examples");
  const ref = examples.data?.[0];
  const seq = ref?.fasta.split("\n").slice(1).join("") ?? "";
  return (
    <Panel className="overflow-hidden">
      <div className="grid-bg absolute inset-0 opacity-40 [mask-image:radial-gradient(ellipse_at_70%_50%,black,transparent_75%)]" />
      <div className="relative grid gap-6 p-6 sm:p-10 lg:grid-cols-[1.05fr_1fr] lg:items-center">
        <div>
          <motion.div {...fade(0)} className="eyebrow flex items-center gap-2 text-teal">
            <Sparkles className="size-3.5" /> Computing for Bioinformatics · group research project
          </motion.div>
          <motion.h2 {...fade(1)} className="mt-4 text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl xl:text-6xl">
            PET Enzyme Explorer
            <br />
            <span className="bg-gradient-to-r from-teal via-mint to-cyan bg-clip-text text-transparent">Decode Enzymes. Rethink Plastic.</span>
          </motion.h2>
          <motion.div {...fade(2)} className="mt-5 max-w-xl space-y-3 text-base leading-relaxed text-muted">
            <p>
              Polyethylene terephthalate (PET) is the world’s most common polyester: drinks bottles, food trays and textile fibres. It is durable by design,
              so most of it is landfilled, burned or lost to the environment, and mechanical recycling degrades the plastic a little more on every cycle.
            </p>
            <p>
              Some bacteria and fungi make enzymes — PET hydrolases — that cut the ester bonds in PET back to its building blocks. An enzyme good enough to
              work at industrial scale would let the same plastic be rebuilt instead of downgraded. Finding better ones in the laboratory is slow, so this
              project asks how far protein sequence analysis and machine learning can narrow the search before anyone pipettes anything.
            </p>
          </motion.div>
          <motion.div {...fade(3)} className="mt-8 flex flex-wrap items-center gap-3">
            <Button asChild variant="primary" size="lg">
              <Link href="/discovery">
                Analyse a sequence <ArrowRight />
              </Link>
            </Button>
            <Button asChild variant="secondary" size="lg">
              <Link href="/data">Explore the data</Link>
            </Button>
          </motion.div>
        </div>
        <motion.div {...fade(2)} className="relative">
          <div className="relative h-56 overflow-hidden rounded-xl border border-line/70 bg-void/60 sm:h-72">
            {seq ? (
              <HelixCanvas sequence={seq} className="reveal h-full w-full" />
            ) : examples.error ? (
              <ErrorState message={examples.error.message} onRetry={examples.retry} className="h-full justify-center" />
            ) : (
              <Skeleton className="h-full w-full" />
            )}
            <div className="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-void/90 to-transparent" />
            <div className="absolute bottom-3 left-4 right-4 flex flex-wrap items-center justify-between gap-2">
              <div className="font-mono text-[11px] text-muted">
                {ref ? (
                  <>
                    <span className="text-teal">{ref.protein_name}</span> · first 140 of {ref.length} residues · helical projection
                  </>
                ) : examples.error ? (
                  "Reference sequence unavailable"
                ) : (
                  "Loading reference sequence…"
                )}
              </div>
              <InfoTip content="Residues of a real PAZy reference sequence wound on an ideal 3.6-residue helix and coloured by chemical class. Illustrative only: not a solved 3D structure." />
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
            {AA_LEGEND.map((l) => (
              <span key={l.label} className="flex items-center gap-1.5 text-[11px] text-muted">
                <span className="size-2 rounded-full" style={{ background: l.color }} />
                {l.label}
              </span>
            ))}
          </div>
        </motion.div>
      </div>
    </Panel>
  );
}

function Question() {
  return (
    <Panel glow className="overflow-hidden">
      <div className="grid-bg absolute inset-0 opacity-25" />
      <div className="relative p-6 sm:p-9">
        <div className="eyebrow flex items-center gap-2 text-teal">
          <HelpCircle className="size-4" /> Research question
        </div>
        <p className="mt-4 max-w-4xl text-xl font-medium leading-snug tracking-tight sm:text-2xl">{RESEARCH_QUESTION}</p>
        <p className="mt-4 max-w-3xl text-sm leading-relaxed text-muted">
          The question is deliberately about <b className="text-ink/90">candidates</b>, not proof. A computational result can say which sequences are worth an
          experiment; only an assay can show that a protein degrades PET.
        </p>
      </div>
    </Panel>
  );
}

function Objectives() {
  return (
    <Panel>
      <PanelHeader eyebrow="Research objectives" title="What the project set out to do" description="Progress against each objective is assessed on the Conclusions page." />
      <div className="grid gap-3 p-5 md:grid-cols-2">
        {OBJECTIVES.map((o, i) => (
          <motion.div key={o.n} {...fade(i)} className="hover-card rounded-xl border border-line/70 bg-void/40 p-4">
            <div className="flex items-center gap-2">
              <span className="rounded-md border border-teal/40 bg-teal/10 px-2 py-0.5 font-mono text-[11px] text-teal">{o.n}</span>
              <span className="font-medium">{o.title}</span>
            </div>
            <p className="mt-2 text-[13px] leading-relaxed text-muted">{o.text}</p>
          </motion.div>
        ))}
      </div>
    </Panel>
  );
}

function Hypotheses() {
  return (
    <Panel>
      <PanelHeader
        eyebrow="Hypotheses"
        title="Testable statements"
        description="Each hypothesis links a sequence-derived property to a measurable experimental observation, and names the test used to decide it."
      />
      <div className="flex flex-col gap-3 p-5">
        {HYPOTHESES.map((h) => (
          <div key={h.id} className="hover-card rounded-xl border border-line/70 bg-void/40 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-md border border-cyan/40 bg-cyan/10 px-2 py-0.5 font-mono text-[11px] text-cyan">{h.id}</span>
              <span className="font-mono text-[11px] text-muted">tested by {h.testedBy}</span>
            </div>
            <p className="mt-2 text-sm leading-relaxed text-ink/90">{h.text}</p>
          </div>
        ))}
      </div>
      <div className="px-5 pb-5">
        <Notice>
          Outcomes are reported on the <Link href="/validation" className="text-teal hover:underline">Model Validation</Link> and{" "}
          <Link href="/conclusions" className="text-teal hover:underline">Conclusions</Link> pages, including the hypotheses the data did not support.
        </Notice>
      </div>
    </Panel>
  );
}

function Methodology() {
  return (
    <Panel>
      <PanelHeader eyebrow="Research methodology" title="From raw downloads to candidate enzymes" description="Every stage writes a table to outputs/; the website reads those tables and never recomputes a result." />
      <div className="grid gap-3 p-5 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
        {METHODOLOGY.map((s, i) => (
          <motion.div key={s.n} {...fade(i)} className="hover-card relative rounded-xl border border-line/70 bg-void/40 p-4">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] text-teal/80">{s.n}</span>
              <s.icon className="size-4 text-muted" />
            </div>
            <div className="mt-2.5 text-[13px] font-medium leading-snug">{s.title}</div>
            <p className="mt-1 text-[11px] leading-relaxed text-muted">{s.text}</p>
            {i < METHODOLOGY.length - 1 && (
              <ArrowRight className="absolute -right-2.5 top-1/2 z-10 hidden size-4 -translate-y-1/2 rounded-full bg-surface text-teal xl:block" />
            )}
          </motion.div>
        ))}
      </div>
    </Panel>
  );
}

function Sources() {
  return (
    <Panel>
      <PanelHeader
        eyebrow="Research data sources"
        title="Where the evidence comes from"
        description="Sources are kept apart by evidence status, because a database entry naming an enzyme “PETase” is not the same as a published assay."
        action={<Library className="size-4 text-muted" />}
      />
      <div className="grid gap-3 p-5 md:grid-cols-2">
        {SOURCES.map((s) => (
          <div key={s.name} className="hover-card rounded-xl border border-line/70 bg-void/40 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium">{s.name}</span>
              <Badge color={s.color}>{s.evidence}</Badge>
            </div>
            <p className="mt-2 text-[13px] leading-relaxed text-muted">{s.role}</p>
            {s.url && (
              <a href={s.url} target="_blank" rel="noreferrer" className="mt-2 inline-block font-mono text-[11px] text-cyan hover:underline">
                {s.url.replace("https://", "")}
              </a>
            )}
          </div>
        ))}
      </div>
    </Panel>
  );
}

function DatasetSummary() {
  const overview = useApi<Overview>("/overview");
  const audit = useApi<Audit>("/audit");
  const model = useApi<Modelling>("/modelling");

  if (overview.error)
    return (
      <Panel>
        <ErrorState message={overview.error.message} onRetry={overview.retry} />
      </Panel>
    );

  // Wait for all three sources so a figure never counts up and then switches source.
  const s = !audit.loading && !model.loading ? overview.data?.stats : undefined;
  const a = audit.data?.available ? audit.data : undefined;
  const m = model.data;
  const count = (id: string, v: number) => <CountUp id={`overview:${id}`} value={v} format={num} />;

  const cards = s
    ? [
        {
          label: "Curated PET-active proteins",
          value: count("proteins", s.proteins),
          sub: `${s.publications} publications`,
          hint: "Unique sequences with experimentally reported PET breakdown in at least one published assay (PAZy).",
          color: "#48E1CD",
        },
        {
          label: "Experimental observations",
          value: a?.pazy ? count("assay-rows", a.pazy.assay_rows) : count("pet-assays", s.pet_assays),
          sub: a?.pazy ? `${num(a.pazy.rows_with_positive_measurement)} positive · ${num(a.pazy.rows_all_zero_or_nondetect)} below detection` : `${num(s.assays_detected)} with breakdown detected`,
          hint: "One row per reported PET assay measurement. Below-detection rows are condition-level zeroes for otherwise active enzymes, never proof of inactivity.",
          color: "#4CA8D8",
        },
        {
          label: "Data sources",
          value: "4",
          sub: "PAZy · PlasticDB · UniProt · PETML",
          hint: "Plus the 2025 standardised screening supplement, which is the only single-protocol dataset comparable across proteins.",
          color: "#B49CF5",
        },
        {
          label: "Curated training examples",
          value: m?.dataset ? count("training", m.dataset.n_proteins) : "—",
          sub: m?.dataset ? `${m.dataset.n_positive} detected / ${m.dataset.n_negative} not detected` : "pending model outputs",
          hint: "Proteins from the standardised screen with a label at 60 °C, grouped into homology groups at 70% identity for splitting.",
          color: "#69E8C3",
        },
      ]
    : [];

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {!s
          ? Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-36 rounded-[14px]" />)
          : cards.map((c, i) => (
              <motion.div key={c.label} {...fade(i)}>
                <Panel className="group h-full p-5 transition duration-300 hover:-translate-y-0.5 hover:border-teal/40">
                  <div className="absolute inset-x-5 top-0 h-px" style={{ background: `linear-gradient(90deg, transparent, ${c.color}, transparent)` }} />
                  <div className="eyebrow">{c.label}</div>
                  <div className="tabular mt-2 text-4xl font-semibold tracking-tight" style={{ color: c.color }}>
                    {c.value}
                  </div>
                  <div className="mt-1 text-xs text-muted">{c.sub}</div>
                  <p className="mt-2 text-xs leading-relaxed text-muted">{c.hint}</p>
                </Panel>
              </motion.div>
            ))}
      </div>
      <p className="text-center text-xs text-muted">
        Every figure above is read from the analysis outputs in <span className="font-mono">outputs/</span>. Nothing on this site is estimated or illustrative.
      </p>
    </div>
  );
}

function Insights() {
  const overview = useApi<Overview>("/overview");
  const data = overview.data;
  if (overview.error)
    return (
      <Panel>
        <ErrorState message={overview.error.message} onRetry={overview.retry} />
      </Panel>
    );
  return (
    <Panel className="flex flex-col">
      <PanelHeader
        eyebrow="What the data contains"
        title="Shape of the evidence"
        description="Generated from the processed tables. These are descriptions of the dataset, not conclusions."
        action={<WorkflowIcon className="size-4 text-muted" />}
      />
      <div className="flex flex-col divide-y divide-line/60 px-5 pb-5 pt-2">
        {!data
          ? Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="my-3 h-12" />)
          : data.insights.map((ins) => (
              <div key={ins.label} className="reveal flex gap-4 py-3">
                <div className="tabular w-20 shrink-0 text-right text-lg font-semibold text-teal">{ins.value}</div>
                <div className="min-w-0">
                  <div className="text-sm font-medium">{ins.label}</div>
                  <p className="text-xs leading-relaxed text-muted">{ins.detail}</p>
                </div>
              </div>
            ))}
      </div>
    </Panel>
  );
}

export function OverviewView() {
  return (
    <div className="flex flex-col gap-6">
      <Hero />
      <Question />
      <DatasetSummary />
      <Objectives />
      <div className="grid gap-6 xl:grid-cols-[1.25fr_1fr]">
        <Hypotheses />
        <Insights />
      </div>
      <Methodology />
      <Sources />
    </div>
  );
}
