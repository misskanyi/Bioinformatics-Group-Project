"use client";

import { Dna } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { EmptyState, InfoTip, Notice, Panel, PanelHeader } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { MatchResult, ProteinDetail } from "@/types/api";

import { HitDetail } from "./hit-detail";
import { HitList, MatchComparison } from "./hit-list";
import { SequenceEditor } from "./sequence-editor";

function Loading({ length }: { length: number }) {
  return (
    <Panel className="overflow-hidden p-8">
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="relative h-10 w-full max-w-md overflow-hidden rounded-md border border-line/70 bg-void/60 font-mono text-[11px] leading-10 text-teal/70">
          <motion.div
            className="absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-teal/25 to-transparent"
            animate={{ x: ["-100%", "300%"] }}
            transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
          />
          Smith–Waterman · BLOSUM62
        </div>
        <div>
          <p className="font-medium">Aligning your {length}-residue sequence against every reference protein</p>
          <p className="mt-1 text-sm text-muted">
            Local alignment to all 298 PET-active references, then a shuffled-sequence control for the top hits. Usually under a second.
          </p>
        </div>
      </div>
    </Panel>
  );
}

export function SequenceLabView() {
  const params = useSearchParams();
  const [input, setInput] = useState("");
  const [result, setResult] = useState<MatchResult | null>(null);
  const [selected, setSelected] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();
  const resultsRef = useRef<HTMLDivElement>(null);

  const analyse = useCallback(async (text: string) => {
    setLoading(true);
    setError(undefined);
    try {
      const r = await api.post<MatchResult>("/sequence/match", { sequence: text, top_n: 5 });
      setResult(r);
      setSelected(1);
      requestAnimationFrame(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (e) {
      setError((e as ApiError).message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, []);

  // /sequence-lab?protein=ID loads that reference sequence and runs the search
  const pid = params.get("protein");
  useEffect(() => {
    if (!pid) return;
    api
      .get<ProteinDetail>(`/proteins/${pid}`)
      .then((p) => {
        const fasta = `>${p.protein_id} ${p.protein_name} | PAZy reference sequence\n${p.sequence}`;
        setInput(fasta);
        analyse(fasta);
      })
      .catch((e: ApiError) => setError(e.message));
  }, [pid, analyse]);

  const hit = result?.hits.find((h) => h.rank === selected);
  const queryLabel = "Query";
  const queryTitle = result?.header && result.header !== "query" ? result.header : "Unnamed query";
  const selfMatch = result?.hits[0] && result.hits[0].identity === 1 && result.hits[0].query_coverage === 1 && result.hits[0].target_coverage === 1;

  return (
    <div className="flex flex-col gap-6">
      <SequenceEditor
        value={input}
        onChange={(v) => {
          setInput(v);
          setError(undefined);
        }}
        onAnalyse={() => analyse(input)}
        loading={loading}
        serverError={error}
      />

      <div ref={resultsRef} className="scroll-mt-20">
        <AnimatePresence mode="wait">
          {loading ? (
            <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <Loading length={input.replace(/^>.*$/m, "").replace(/\s/g, "").length} />
            </motion.div>
          ) : result && hit ? (
            <motion.div key="results" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-6">
              {selfMatch && (
                <Notice>
                  Your query is identical to reference protein <b>{result.hits[0].protein_name}</b>, which is part of the characterised set.
                </Notice>
              )}
              <div className="grid gap-6 xl:grid-cols-[400px_1fr]">
                <div className="flex flex-col gap-6">
                  <Panel>
                    <PanelHeader eyebrow="Submitted protein" title={<span className="break-all font-mono text-sm">{queryTitle}</span>} />
                    <div className="grid grid-cols-2 gap-4 p-5 pt-4">
                      <div>
                        <div className="eyebrow">Length</div>
                        <div className="tabular mt-1 font-mono text-2xl font-semibold text-teal">{result.length} aa</div>
                      </div>
                      <div>
                        <div className="eyebrow">References searched</div>
                        <div className="tabular mt-1 font-mono text-2xl font-semibold text-cyan">{result.method.reference_set_size}</div>
                      </div>
                      <div className="col-span-2 break-all rounded-md bg-void/60 p-2 font-mono text-[10px] leading-4 text-muted">
                        {result.sequence.slice(0, 120)}
                        {result.sequence.length > 120 && "…"}
                      </div>
                    </div>
                  </Panel>
                  <Panel>
                    <PanelHeader
                      eyebrow="Top matches"
                      title="Closest characterised proteins"
                      action={<InfoTip content={`Ranked by ${result.method.ranking}.`} />}
                    />
                    <div className="p-4">
                      <HitList hits={result.hits} method={result.method} selected={selected} onSelect={setSelected} />
                    </div>
                  </Panel>
                </div>
                <Panel className="min-w-0">
                  <AnimatePresence mode="wait">
                    <motion.div key={hit.rank} initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
                      <HitDetail hit={hit} method={result.method} queryLabel={queryLabel} />
                    </motion.div>
                  </AnimatePresence>
                </Panel>
              </div>
              <Panel>
                <PanelHeader
                  eyebrow="Match comparison"
                  title="Five closest proteins side by side"
                  description="Identity counts identical residues over aligned columns. Coverage shows how much of each sequence the alignment spans: high identity over a short stretch is weak evidence of homology."
                />
                <div className="p-5">
                  <MatchComparison hits={result.hits} method={result.method} />
                  <div className="mt-4 grid gap-2 sm:grid-cols-3">
                    {result.method.bands.map((b, i) => (
                      <div key={b.label} className="rounded-lg border border-line/60 bg-void/40 p-3 text-xs">
                        <div className="font-medium" style={{ color: ["#48E1CD", "#4CA8D8", "#E8B56B"][i] }}>
                          {b.label}
                        </div>
                        <div className="mt-1 text-muted">
                          ≥ {b.min_identity * 100}% identity and ≥ {b.min_coverage * 100}% coverage of both sequences
                        </div>
                      </div>
                    ))}
                  </div>
                  <p className="mt-3 text-xs text-muted">
                    Otherwise: “{result.method.no_match_label}”. 25–40% identity is the twilight zone where homology cannot be inferred from identity alone
                    (Rost, 1999).
                  </p>
                </div>
              </Panel>
            </motion.div>
          ) : (
            <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <Panel>
                <EmptyState title="No analysis yet" icon={<Dna className="size-5" />}>
                  Paste a protein sequence or load a reference example, then choose <b className="text-ink">Analyse Sequence</b>. Results list the closest
                  experimentally characterised PET-active proteins and the evidence reported for them.
                </EmptyState>
              </Panel>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
