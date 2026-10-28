"use client";

import { ArrowRight, Dna, Microscope, Share2, Sparkles, Thermometer } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { ErrorState, InfoTip, Panel, PanelHeader, Skeleton } from "@/components/ui/primitives";
import { AA_LEGEND, HelixCanvas } from "@/components/viz/helix-canvas";
import { NetworkGraph } from "@/components/viz/network-graph";
import { useApi } from "@/lib/api";
import { clusterColor } from "@/lib/palette";
import { num } from "@/lib/utils";
import type { Example, NetworkData, Overview } from "@/types/api";

const WORKFLOW = [
  { n: "01", title: "Sequence Matching", href: "/sequence-lab", icon: Dna, text: "Align a query against every characterised PET-active reference protein." },
  { n: "02", title: "Molecular Clustering", href: "/networks", icon: Share2, text: "Place it in sequence groups and the similarity network." },
  { n: "03", title: "Experimental Conditions", href: "/conditions", icon: Thermometer, text: "Review reported assay temperatures, pH and outcomes." },
  { n: "04", title: "Biological Sources", href: "/organisms", icon: Microscope, text: "See which organisms are documented for matching proteins." },
];

const fade = (i: number) => ({
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  transition: { delay: 0.05 * i, duration: 0.45, ease: [0.22, 1, 0.36, 1] as const },
});

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
            <Sparkles className="size-3.5" /> PET-hydrolase evidence workspace
          </motion.div>
          <motion.h2 {...fade(1)} className="mt-4 text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl xl:text-6xl">
            Decode Enzymes.
            <br />
            <span className="bg-gradient-to-r from-teal via-mint to-cyan bg-clip-text text-transparent">Rethink Plastic.</span>
          </motion.h2>
          <motion.p {...fade(2)} className="mt-5 max-w-xl text-base leading-relaxed text-muted sm:text-lg">
            Explore PET-degrading enzymes through protein sequence analysis, molecular relationships and experimental evidence.
          </motion.p>
          <motion.div {...fade(3)} className="mt-8 flex flex-wrap items-center gap-3">
            <Button asChild variant="primary" size="lg">
              <Link href="/sequence-lab">
                Launch Sequence Analysis <ArrowRight />
              </Link>
            </Button>
            <Button asChild variant="secondary" size="lg">
              <Link href="/datasets">How results were produced</Link>
            </Button>
          </motion.div>
        </div>
        <motion.div {...fade(2)} className="relative">
          <div className="relative h-56 overflow-hidden rounded-xl border border-line/70 bg-void/60 sm:h-72">
            {seq ? <HelixCanvas sequence={seq} className="h-full w-full" /> : <Skeleton className="h-full w-full" />}
            <div className="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-void/90 to-transparent" />
            <div className="absolute bottom-3 left-4 right-4 flex flex-wrap items-center justify-between gap-2">
              <div className="font-mono text-[11px] text-muted">
                {ref ? (
                  <>
                    <span className="text-teal">{ref.protein_name}</span> · first 140 of {ref.length} residues · helical projection
                  </>
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

function Stats({ data }: { data?: Overview }) {
  const s = data?.stats;
  const cards = s
    ? [
        { label: "PET-active sequences", value: num(s.proteins), hint: "Usable proteins with experimentally reported PET breakdown and a valid sequence (PAZy).", color: "#48E1CD" },
        { label: "Supporting publications", value: num(s.publications), hint: "Distinct DOIs reporting PET assays for these proteins.", color: "#4CA8D8" },
        { label: "Sequence groups", value: `${s.clusters}`, sub: `${s.subclusters} subgroups`, hint: "Clusters from average-linkage clustering of pairwise alignment distances; the largest is split into two subgroups.", color: "#69E8C3" },
        { label: "Documented organisms", value: num(s.proteins_with_organism), sub: `${s.organism_names} organism names`, hint: "Proteins whose sequence matches a database record naming the source organism. The rest stay unknown.", color: "#B49CF5" },
      ]
    : [];
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {!s
        ? Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-36 rounded-[14px]" />)
        : cards.map((c, i) => (
            <motion.div key={c.label} {...fade(i)}>
              <Panel className="group h-full p-5 transition hover:-translate-y-0.5 hover:border-teal/40">
                <div className="absolute inset-x-5 top-0 h-px" style={{ background: `linear-gradient(90deg, transparent, ${c.color}, transparent)` }} />
                <div className="eyebrow">{c.label}</div>
                <div className="tabular mt-2 flex items-baseline gap-2">
                  <span className="text-4xl font-semibold tracking-tight" style={{ color: c.color }}>
                    {c.value}
                  </span>
                  {c.sub && <span className="text-xs text-muted">{c.sub}</span>}
                </div>
                <p className="mt-2 text-xs leading-relaxed text-muted">{c.hint}</p>
              </Panel>
            </motion.div>
          ))}
    </div>
  );
}

function Workflow() {
  return (
    <Panel>
      <PanelHeader eyebrow="Research workflow" title="From a sequence to its evidence" />
      <div className="grid gap-3 p-5 sm:grid-cols-2 xl:grid-cols-4">
        {WORKFLOW.map((w, i) => (
          <Link
            key={w.n}
            href={w.href}
            className="group relative rounded-xl border border-line/80 bg-void/40 p-4 transition hover:border-teal/50 hover:bg-elevated/50"
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-teal/80">{w.n}</span>
              <w.icon className="size-5 text-muted transition group-hover:text-teal" />
            </div>
            <div className="mt-3 font-medium">{w.title}</div>
            <p className="mt-1 text-xs leading-relaxed text-muted">{w.text}</p>
            <ArrowRight className="mt-3 size-4 text-muted transition group-hover:translate-x-1 group-hover:text-teal" />
            {i < WORKFLOW.length - 1 && (
              <div className="absolute -right-2 top-1/2 hidden h-px w-4 bg-gradient-to-r from-teal/60 to-transparent xl:block" />
            )}
          </Link>
        ))}
      </div>
    </Panel>
  );
}

function NetworkPreview() {
  const router = useRouter();
  const net = useApi<NetworkData>("/network?min_identity=0.6&min_coverage=0.7");
  return (
    <Panel className="flex flex-col">
      <PanelHeader
        eyebrow="Molecular relationships"
        title="Sequence-similarity network"
        description="Each node is a protein; each line joins two proteins with ≥ 60% identity over ≥ 70% of both sequences."
        action={
          <Button asChild size="sm" variant="outline">
            <Link href="/networks">
              Open explorer <ArrowRight />
            </Link>
          </Button>
        }
      />
      <div className="relative m-5 mt-4 h-72 flex-1 overflow-hidden rounded-xl border border-line/70 bg-void/70 xl:h-auto xl:min-h-72">
        {net.error ? (
          <ErrorState message={net.error.message} onRetry={net.retry} />
        ) : net.data ? (
          <NetworkGraph data={net.data} preview onSelect={(id) => id != null && router.push(`/networks?protein=${id}`)} />
        ) : (
          <Skeleton className="h-full w-full" />
        )}
        {net.data && (
          <div className="pointer-events-none absolute bottom-2 left-3 font-mono text-[10px] text-muted">
            {net.data.nodes.length} proteins · {num(net.data.stats.edges)} edges · click a node to inspect
          </div>
        )}
      </div>
    </Panel>
  );
}

function Insights({ data }: { data?: Overview }) {
  return (
    <Panel className="flex flex-col">
      <PanelHeader eyebrow="Scientific insight" title="What the data contains" description="Generated from the processed tables; no conclusions are added." />
      <div className="flex flex-col divide-y divide-line/60 px-5 pb-3 pt-2">
        {!data
          ? Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="my-3 h-12" />)
          : data.insights.map((ins) => (
              <div key={ins.label} className="flex gap-4 py-3">
                <div className="tabular w-20 shrink-0 text-right text-lg font-semibold text-teal">{ins.value}</div>
                <div className="min-w-0">
                  <div className="text-sm font-medium">{ins.label}</div>
                  <p className="text-xs leading-relaxed text-muted">{ins.detail}</p>
                </div>
              </div>
            ))}
      </div>
      {data && (
        <div className="mt-auto px-5 pb-5">
          <div className="eyebrow mb-2">Proteins per subgroup</div>
          <div className="flex h-3 overflow-hidden rounded-full">
            {data.cluster_sizes.map((c) => (
              <div
                key={c.subcluster}
                title={`${c.subcluster}: ${c.n} proteins`}
                style={{ width: `${(100 * c.n) / data.stats.proteins}%`, background: clusterColor(c.subcluster) }}
                className="min-w-[3px] border-r border-void"
              />
            ))}
          </div>
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
            {data.cluster_sizes.map((c) => (
              <span key={c.subcluster} className="font-mono text-[10px] text-muted">
                <span style={{ color: clusterColor(c.subcluster) }}>■</span> {c.subcluster} {c.n}
              </span>
            ))}
          </div>
        </div>
      )}
    </Panel>
  );
}

export function DashboardView() {
  const overview = useApi<Overview>("/overview");
  return (
    <div className="flex flex-col gap-6">
      <Hero />
      {overview.error ? (
        <Panel>
          <ErrorState message={overview.error.message} onRetry={overview.retry} />
        </Panel>
      ) : (
        <Stats data={overview.data} />
      )}
      <Workflow />
      <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <NetworkPreview />
        <Insights data={overview.data} />
      </div>
      <p className="text-center text-xs text-muted">
        Evidence explorer, not a validated PET-activity predictor. No PET-inactive sequences are available, so similarity is never
        converted into a probability of activity.
      </p>
    </div>
  );
}
