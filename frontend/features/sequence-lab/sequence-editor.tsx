"use client";

import { Eraser, FlaskConical, Loader2, Play } from "lucide-react";
import { useMemo, useRef } from "react";

import { Button } from "@/components/ui/button";
import { Badge, Panel, PanelHeader, Skeleton } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Example } from "@/types/api";

import { localCheck, RESIDUE_CLASS, residueColor, STANDARD_AA } from "./residues";

const MIN = 30;
const MAX = 5000;

/** Coloured mirror of the textarea content (same font, wrapping and padding). */
function Highlight({ text }: { text: string }) {
  return (
    <>
      {text.split("\n").map((line, i) => (
        <span key={i}>
          {line.trimStart().startsWith(">") ? (
            <span className="text-muted">{line}</span>
          ) : (
            line.split("").map((c, j) => {
              const u = c.toUpperCase();
              const col = residueColor(u);
              const bad = !col && !/[\s\d*]/.test(c);
              return (
                <span key={j} style={col ? { color: col } : undefined} className={bad ? "rounded-sm bg-rose/30 text-rose" : undefined}>
                  {c}
                </span>
              );
            })
          )}
          {"\n"}
        </span>
      ))}
    </>
  );
}

export function SequenceEditor({
  value,
  onChange,
  onAnalyse,
  loading,
  serverError,
}: {
  value: string;
  onChange: (v: string) => void;
  onAnalyse: () => void;
  loading: boolean;
  serverError?: string;
}) {
  const examples = useApi<Example[]>("/sequence/examples");
  const mirror = useRef<HTMLPreElement>(null);
  const check = useMemo(() => localCheck(value), [value]);
  const len = check.sequence.length;

  const problem = !value.trim()
    ? null
    : check.multiple
      ? "Enter one sequence only — several FASTA headers were found."
      : check.looksNucleotide
        ? "This looks like a DNA/RNA sequence. Enter an amino-acid sequence."
        : check.invalid.length
          ? `Invalid characters: ${check.invalid.join(", ")}. Only the 20 standard amino-acid letters are accepted.`
          : len < MIN
            ? `Sequence too short (${len} aa). Minimum is ${MIN} aa.`
            : len > MAX
              ? `Sequence too long (${len} aa). Maximum is ${MAX} aa.`
              : null;

  const composition = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const c of check.sequence) {
      if (!STANDARD_AA.has(c)) continue;
      const key = Object.entries(RESIDUE_CLASS).find(([, v]) => v.color === residueColor(c))?.[0] ?? "other";
      counts[key] = (counts[key] ?? 0) + 1;
    }
    return counts;
  }, [check.sequence]);

  return (
    <Panel glow={!!value && !problem}>
      <PanelHeader
        eyebrow="Query input"
        title="Protein sequence"
        description="Paste a single amino-acid sequence as plain text or FASTA. Spaces, numbers and a terminal * are ignored."
        action={
          <div className="flex flex-wrap items-center gap-2">
            {examples.data ? (
              examples.data.map((e) => (
                <Button key={e.protein_id} size="sm" variant="ghost" onClick={() => onChange(e.fasta)} title={`Load the PAZy reference sequence of ${e.protein_name}`}>
                  <FlaskConical /> {e.protein_name}
                </Button>
              ))
            ) : (
              <Skeleton className="h-8 w-40" />
            )}
          </div>
        }
      />
      <div className="p-5">
        <div className="relative overflow-hidden rounded-xl border border-line bg-void/80 focus-within:border-teal/60 focus-within:ring-2 focus-within:ring-teal/15">
          <pre
            ref={mirror}
            aria-hidden
            className="pointer-events-none absolute inset-0 m-0 overflow-hidden whitespace-pre-wrap break-all p-4 font-mono text-[13px] leading-6"
          >
            <Highlight text={value} />
          </pre>
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onScroll={(e) => {
              if (mirror.current) mirror.current.scrollTop = e.currentTarget.scrollTop;
            }}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && !problem && value.trim()) onAnalyse();
            }}
            spellCheck={false}
            autoCapitalize="characters"
            aria-label="Protein sequence input"
            aria-invalid={!!problem}
            placeholder={">query_name\nPaste a single protein sequence (one-letter amino-acid code)…"}
            className="relative block h-64 w-full resize-y whitespace-pre-wrap break-all bg-transparent p-4 font-mono text-[13px] leading-6 text-transparent caret-teal placeholder:text-muted/35 focus:outline-none sm:h-72"
          />
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
          <div className="tabular font-mono text-xs text-muted">
            <span className={cn("text-sm font-semibold", len ? "text-teal" : "text-muted")}>{len}</span> aa
            {check.header && <span className="ml-3">FASTA · {check.header.slice(0, 40)}</span>}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(RESIDUE_CLASS).map(([k, v]) => (
              <span key={k} className="flex items-center gap-1 font-mono text-[10px] text-muted" title={v.name}>
                <span className="size-1.5 rounded-full" style={{ background: v.color }} />
                {v.name.split(" (")[0]}
                {len > 0 && <span className="text-ink/70">{(((composition[k] ?? 0) / len) * 100).toFixed(0)}%</span>}
              </span>
            ))}
          </div>
        </div>

        {(problem || serverError) && (
          <div role="alert" className="mt-3 rounded-lg border border-amber/40 bg-amber/[0.07] px-3 py-2 text-sm text-amber">
            {serverError ?? problem}
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button variant="primary" size="lg" onClick={onAnalyse} disabled={!value.trim() || !!problem || loading}>
            {loading ? <Loader2 className="animate-spin" /> : <Play />}
            {loading ? "Aligning…" : "Analyse Sequence"}
          </Button>
          <Button variant="ghost" onClick={() => onChange("")} disabled={!value || loading}>
            <Eraser /> Clear
          </Button>
          <span className="hidden font-mono text-[11px] text-muted sm:inline">⌘/Ctrl + Enter</span>
          <Badge color="#4CA8D8" className="ml-auto">
            Computational similarity only
          </Badge>
        </div>
      </div>
    </Panel>
  );
}
