"use client";

import { Beaker, Dna, FlaskConical, Hourglass, Layers, Thermometer } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Badge, EmptyState, LoadingState, Notice, Panel, PanelHeader, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/primitives";
import { BulkAnalysis } from "@/features/discovery/bulk/bulk-analysis";
import { SequenceLabView } from "@/features/sequence-lab/sequence-lab-view";
import { useApi } from "@/lib/api";
import { num } from "@/lib/utils";
import type { Audit, Modelling } from "@/types/api";

/* ---------------------------------------------------------- prediction conditions */

function Conditions() {
  const audit = useApi<Audit>("/audit");
  const rows = audit.data?.available ? audit.data.condition_labels ?? [] : [];
  const best = [...rows].sort((a, b) => b.n - a.n || b.pos_rate - a.pos_rate)[0];

  return (
    <Panel>
      <PanelHeader
        eyebrow="Experimental conditions"
        title="What a prediction would have to be about"
        description="PET activity is condition-dependent, so a model can only be trained to answer a question with a substrate, a temperature and a pH attached."
        action={<Thermometer className="size-4 text-muted" />}
      />
      <div className="grid gap-4 p-5 lg:grid-cols-[1fr_1.2fr]">
        <div className="rounded-xl border border-line/70 bg-void/40 p-4">
          <div className="eyebrow mb-3">Proposed assay condition</div>
          <dl className="flex flex-col gap-2 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-muted">Substrate</dt>
              <dd className="font-mono text-ink">crystalline PET powder</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-muted">Temperature</dt>
              <dd className="font-mono text-ink">40 °C</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-muted">pH</dt>
              <dd className="font-mono text-ink">6.5</dd>
            </div>
          </dl>
          {best && (
            <p className="mt-3 text-xs leading-relaxed text-muted">
              This condition exists in the curated screen with {num(best.n)} enzymes assayed and a {Math.round(best.pos_rate * 100)}% positive rate, which is
              why it was proposed. It is <b className="text-ink/90">not</b> the condition the current model was fitted to.
            </p>
          )}
        </div>
        <div className="rounded-xl border border-amber/30 bg-amber/[0.05] p-4">
          <div className="eyebrow mb-3 text-amber">What the trained model actually targets</div>
          <p className="text-[13px] leading-relaxed text-ink/85">
            The model in this repository was fitted to a different label: <b>PET conversion still detected at 60 °C</b> on crystalline powder, in the same
            standardised screen. Temperature and pH are therefore fixed by the training data — they are not inputs a user can choose, and the interface does
            not pretend otherwise.
          </p>
          <p className="mt-2 text-[13px] leading-relaxed text-muted">
            A condition-selectable predictor would need one model per condition, each validated separately. That is listed as future work.
          </p>
        </div>
      </div>
    </Panel>
  );
}

/* ---------------------------------------------------------- prediction (unavailable) */

function Prediction() {
  const res = useApi<Modelling>("/modelling");
  const m = res.data;

  if (res.loading)
    return (
      <Panel>
        <LoadingState title="Loading machine-learning validation outputs">Checking whether a validated model is available to score sequences.</LoadingState>
      </Panel>
    );

  const perm = m?.permutation_test;
  const best = m?.best_model;

  return (
    <Panel>
      <PanelHeader
        eyebrow="Machine-learning prediction"
        title="Activity prediction"
        description="A predicted class or probability is only shown when a model has been validated well enough for the number to mean something."
        action={<Badge color="var(--color-amber)">Unavailable</Badge>}
      />
      <div className="p-5">
        <EmptyState variant="unavailable" title="No validated model is available to score your sequence" icon={<Hourglass className="size-5" />}>
          <p>
            The classifier trained on sequence features does not separate the two classes better than chance under homology-aware cross-validation
            {best ? ` (best model: ${best.model}, ROC AUC ${best.roc_auc_mean.toFixed(3)} ± ${best.roc_auc_sd.toFixed(3)})` : ""}
            {perm ? `, and a ${perm.n_permutations}-draw label-permutation test gives p = ${perm.empirical_p}` : ""}. Producing a probability from it would
            put a confident-looking number on noise, so this panel stays empty on purpose.
          </p>
          <p className="mt-3">
            The full evidence is on the <Link href="/validation" className="text-teal hover:underline">Model Validation</Link> page. Sequence similarity to
            characterised enzymes, below, is the evidence this project <i>can</i> stand behind.
          </p>
        </EmptyState>
      </div>
    </Panel>
  );
}

/* ---------------------------------------------------------- candidates (pending) */

function Candidates() {
  const res = useApi<Modelling>("/modelling");
  const c = res.data?.candidates;

  return (
    <Panel>
      <PanelHeader
        eyebrow="Candidate discovery"
        title="Ranked untested candidates"
        description="Previously untested sequences, ordered by predicted activity, for laboratory follow-up."
        action={<Badge color="var(--color-amber)">Pending model outputs</Badge>}
      />
      <div className="p-5">
        {res.loading ? (
          <LoadingState title="Loading candidate discovery results" />
        ) : (
          <EmptyState variant="unavailable" title="No candidate ranking is published" icon={<FlaskConical className="size-5" />}>
            <p>{c?.reason}</p>
            {c?.pool != null && (
              <p className="mt-3">
                The candidate pool is identified and ready: <b className="text-ink">{num(c.pool)}</b> sequences in the 2025 screening library that were never
                assayed. {c.pool_source}
              </p>
            )}
            <p className="mt-3">
              Until a model clears its null, the defensible way to shortlist a protein is its measured relationship to characterised enzymes — alignment
              identity, coverage and the assay evidence reported for the nearest matches.
            </p>
          </EmptyState>
        )}
      </div>
    </Panel>
  );
}

/* ---------------------------------------------------------- page */

type Mode = "single" | "bulk";

export function DiscoveryView() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const mode: Mode = params.get("mode") === "bulk" ? "bulk" : "single";
  const setMode = (m: string) => {
    const sp = new URLSearchParams(params.toString());
    if (m === "bulk") sp.set("mode", "bulk");
    else sp.delete("mode");
    router.replace(sp.size ? `${pathname}?${sp}` : pathname, { scroll: false });
  };

  return (
    <div className="flex flex-col gap-6">
      <Notice>
        Two different things live on this page. <b>Sequence similarity</b> is measured and reproducible. A <b>machine-learning prediction</b> would be an
        inference about an unseen experiment — and is shown only when the validation supports it.
      </Notice>

      <Panel className="overflow-hidden">
        <div className="grid-bg absolute inset-0 opacity-30 [mask-image:radial-gradient(ellipse_at_80%_0%,black,transparent_70%)]" />
        <div className="relative p-6 sm:p-8">
          <div className="eyebrow flex items-center gap-2 text-teal">
            <Beaker className="size-4" /> Enzyme prediction &amp; discovery
          </div>
          <h2 className="mt-3 max-w-3xl text-2xl font-semibold tracking-tight sm:text-3xl">Place an unknown protein among the characterised PET enzymes</h2>
          <p className="mt-3 max-w-3xl text-sm leading-relaxed text-muted">
            Paste an amino-acid sequence or load a reference example, or upload a whole dataset under Bulk Analysis. Each sequence is aligned against every
            curated PET-active protein with Smith–Waterman and BLOSUM62, and the closest matches are reported with their identity, coverage and the published
            assay evidence behind them, alongside its composition, physicochemical properties and catalytic-motif search.
          </p>
        </div>
      </Panel>

      {/* both panes stay mounted so switching tabs never discards an analysis in progress */}
      <Tabs value={mode} onValueChange={setMode} className="flex flex-col gap-6">
        <TabsList aria-label="Analysis mode" className="self-start">
          <TabsTrigger value="single" className="flex items-center gap-1.5 px-4 py-2 text-[13px]">
            <Dna className="size-4" /> Single Sequence
          </TabsTrigger>
          <TabsTrigger value="bulk" className="flex items-center gap-1.5 px-4 py-2 text-[13px]">
            <Layers className="size-4" /> Bulk Analysis
          </TabsTrigger>
        </TabsList>
        <TabsContent value="single" forceMount className="reveal focus-visible:outline-none data-[state=inactive]:hidden">
          <SequenceLabView />
        </TabsContent>
        <TabsContent value="bulk" forceMount className="reveal focus-visible:outline-none data-[state=inactive]:hidden">
          <BulkAnalysis />
        </TabsContent>
      </Tabs>

      <Conditions />
      <Prediction />
      <Candidates />

      <Panel>
        <PanelHeader
          eyebrow="Biological interpretation"
          title="How to read a strong match"
          description="What a high-identity hit does and does not tell you about a protein."
        />
        <div className="grid gap-4 p-5 md:grid-cols-2">
          <div className="rounded-xl border border-mint/25 bg-mint/[0.05] p-4 transition-colors duration-200 hover:border-mint/45">
            <div className="eyebrow mb-2 text-mint">Supporting evidence</div>
            <ul className="flex flex-col gap-2 text-[13px] leading-relaxed text-ink/85">
              <li>High identity over most of both sequences points to a shared fold and, usually, a shared catalytic mechanism.</li>
              <li>The G-x-S-x-G motif around the catalytic serine is carried by 296 of the 298 curated proteins; its absence in a query is a warning sign.</li>
              <li>Matching a protein with many independent publications is stronger evidence than matching one described once.</li>
              <li>If the nearest relatives were active at the temperature you care about, that condition is at least plausible for the query.</li>
            </ul>
          </div>
          <div className="rounded-xl border border-amber/30 bg-amber/[0.05] p-4 transition-colors duration-200 hover:border-amber/50">
            <div className="eyebrow mb-2 text-amber">What it cannot show</div>
            <ul className="flex flex-col gap-2 text-[13px] leading-relaxed text-ink/85">
              <li>Single substitutions in or near the active site can abolish activity while leaving identity above 99%.</li>
              <li>Identity in the 25–40% twilight zone cannot establish homology on its own.</li>
              <li>Expression, solubility and stability decide whether an enzyme works in practice, and none of them are visible in a pairwise alignment.</li>
              <li>No alignment can give a probability of PET degradation, because no validated PET-inactive reference set exists to calibrate one.</li>
            </ul>
          </div>
        </div>
      </Panel>
    </div>
  );
}
