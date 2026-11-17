"use client";

import { AlertTriangle, Ban, BookOpen, CheckCircle2, ChevronDown, HelpCircle, Info, ListChecks, ShieldAlert, XCircle } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { C, tint } from "@/lib/palette";
import { cn, pct } from "@/lib/utils";
import type { Assessment, AssessmentCategory, BatchResult, EvidenceRules } from "@/types/api";

/**
 * Sequence-based evidence assessment. Colours are assigned by the backend
 * (pet_explorer/evidence.py) from computed alignment results; the UI only displays them.
 */
export type UiCategory = AssessmentCategory | "invalid";

export const ASSESSMENT: Record<UiCategory, { label: string; short: string; color: string; icon: LucideIcon; blurb: string }> = {
  green: {
    label: "Likely PET-degrading candidate",
    short: "Likely candidate",
    color: C.mint,
    icon: CheckCircle2,
    blurb: "Strong sequence evidence linking it to a characterised PET-degrading enzyme.",
  },
  yellow: {
    label: "Possible PET-degrading candidate",
    short: "Possible candidate",
    color: C.amber,
    icon: AlertTriangle,
    blurb: "Some supporting evidence, but incomplete, weak or ambiguous.",
  },
  red: {
    label: "Unlikely based on current evidence",
    short: "Unlikely (current evidence)",
    color: C.rose,
    icon: XCircle,
    blurb: "No convincing similarity to characterised PET-degrading enzymes. Not proof of inactivity.",
  },
  insufficient: {
    label: "Insufficient evidence",
    short: "Insufficient evidence",
    color: C.slate,
    icon: HelpCircle,
    blurb: "The signals conflict or are too partial to assign a colour reliably.",
  },
  invalid: {
    label: "Invalid sequence",
    short: "Invalid",
    color: C.slate,
    icon: Ban,
    blurb: "The record could not be analysed.",
  },
};

export const CATEGORY_ORDER: UiCategory[] = ["green", "yellow", "red", "insufficient", "invalid"];

export const DISCLAIMER =
  "These indicators are based on sequence similarity and available experimental evidence. They are not validated predictions of PET-degrading activity. Laboratory testing is required to confirm activity.";

/** Category for a batch row; undefined while the row is still pending. */
export function categoryOf(r: BatchResult): UiCategory | undefined {
  if (r.assessment) return r.assessment.category;
  if (r.status === "invalid" || r.status === "error") return "invalid";
  return undefined;
}

export function AssessmentBadge({ category, known, short, className }: { category?: UiCategory; known?: boolean; short?: boolean; className?: string }) {
  if (!category) return <span className="text-xs text-muted">—</span>;
  const a = ASSESSMENT[category];
  const Icon = a.icon;
  return (
    <span className={cn("inline-flex flex-wrap items-center gap-1", className)}>
      <Badge color={a.color} dot={false} className="whitespace-nowrap">
        <Icon className="size-3.5" aria-hidden />
        {short ? a.short : a.label}
      </Badge>
      {known && (
        <Badge color={C.sky} dot={false} className="whitespace-nowrap">
          <BookOpen className="size-3" aria-hidden /> Known reference
        </Badge>
      )}
    </span>
  );
}

function List({ title, icon: Icon, items }: { title: string; icon: LucideIcon; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <div className="eyebrow mb-2 flex items-center gap-1.5">
        <Icon className="size-3.5" aria-hidden /> {title}
      </div>
      <ul className="flex list-disc flex-col gap-1.5 pl-5 text-[13px] leading-relaxed text-ink/85 marker:text-muted">
        {items.map((t) => (
          <li key={t}>{t}</li>
        ))}
      </ul>
    </div>
  );
}

/** Full explanation: verdict, why, limitations, next steps. Used by single-sequence and bulk views. */
export function AssessmentPanel({ assessment, compact }: { assessment: Assessment; compact?: boolean }) {
  const a = ASSESSMENT[assessment.category];
  const Icon = a.icon;
  const m = assessment.metrics;
  return (
    <section
      aria-label={`Evidence assessment: ${a.label}`}
      className="rounded-xl border p-4 sm:p-5"
      style={{ borderColor: tint(a.color, 40), background: tint(a.color, 6) }}
    >
      <div className="flex flex-wrap items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-full" style={{ background: tint(a.color, 16), color: a.color }}>
          <Icon className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <div className="eyebrow">Sequence-based evidence assessment</div>
          <div className="mt-0.5 flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-semibold tracking-tight" style={{ color: a.color }}>
              {a.label}
            </h3>
            {assessment.known_reference && (
              <Badge color={C.sky} dot={false}>
                <BookOpen className="size-3" aria-hidden /> Known characterised reference — not a new discovery
              </Badge>
            )}
          </div>
          <p className="mt-2 text-[13px] leading-relaxed text-ink/90">{assessment.summary}</p>
        </div>
      </div>

      {m && (
        <dl className="mt-4 grid grid-cols-2 gap-3 rounded-lg border border-line/60 bg-void/40 p-3 text-xs sm:grid-cols-5">
          <div>
            <dt className="text-muted">Closest PET enzyme</dt>
            <dd className="mt-0.5 font-mono font-semibold text-cyan">{m.closest_reference}</dd>
          </div>
          <div>
            <dt className="text-muted">Identity</dt>
            <dd className="tabular mt-0.5 font-mono">{pct(m.identity)}</dd>
          </div>
          <div>
            <dt className="text-muted">Coverage (query / ref.)</dt>
            <dd className="tabular mt-0.5 font-mono">
              {pct(m.query_coverage, 0)} / {pct(m.target_coverage, 0)}
            </dd>
          </div>
          <div>
            <dt className="text-muted">Shuffle z</dt>
            <dd className="tabular mt-0.5 font-mono">{m.shuffled_z.toFixed(1)}</dd>
          </div>
          <div>
            <dt className="text-muted">G-x-S-x-G motif</dt>
            <dd className="tabular mt-0.5 font-mono">{assessment.motif_count ? `${assessment.motif_count}× found` : "absent"}</dd>
          </div>
        </dl>
      )}

      {!compact && (
        <div className="mt-4 grid gap-5 lg:grid-cols-3">
          <List title="Why this assessment" icon={Info} items={[...assessment.reasons, ...(assessment.rule_condition ? [`Rule ${assessment.rule}: ${assessment.rule_condition}.`] : [])]} />
          <List title="Limitations" icon={ShieldAlert} items={assessment.limitations} />
          <List title="Recommended next steps" icon={ListChecks} items={assessment.next_steps} />
        </div>
      )}
    </section>
  );
}

export function AssessmentDisclaimer({ className }: { className?: string }) {
  return (
    <p role="note" className={cn("flex gap-2 rounded-lg border border-line/70 bg-void/40 px-3.5 py-2.5 text-xs leading-relaxed text-muted", className)}>
      <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
      {DISCLAIMER}
    </p>
  );
}

/** Collapsible, data-driven description of the colour rules and their calibration. */
export function RulesExplainer() {
  const res = useApi<EvidenceRules>("/evidence/rules");
  const r = res.data;
  return (
    <details className="group rounded-xl border border-line/70 bg-void/40 p-4 text-[13px]">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 font-medium text-ink">
        How are the colours assigned?
        <ChevronDown className="size-4 text-muted transition group-open:rotate-180" aria-hidden />
      </summary>
      {res.error && <p className="mt-3 text-rose">{res.error.message}</p>}
      {!r && !res.error && <p className="mt-3 text-muted">Loading rules…</p>}
      {r && (
        <div className="mt-3 flex flex-col gap-3">
          <p className="leading-relaxed text-muted">
            The top hit of a Smith–Waterman / BLOSUM62 search against the curated PET-active reference set is assessed with fixed rules (v{r.version}). Every rule
            combines identity, coverage of both sequences and a z-score against {r.n_shuffles} composition-preserving shuffles. z ≤ {r.z_chance} is within the
            range seen for shuffled sequences; z ≥ {r.z_strong} is above every shuffled control.
          </p>
          {r.calibration && (
            <p className="leading-relaxed text-muted">
              Calibration on {r.calibration.n_per_set} shuffled reference sequences: max z {r.calibration.shuffled_null.z_max}, assessed as{" "}
              {fmtCounts(r.calibration.shuffled_null.categories)}. Leave-one-out search of the {r.calibration.n_per_set} known PET-active proteins (own entry
              removed): {fmtCounts(r.calibration.leave_one_out.categories)} — so a red result can occur for a genuinely active enzyme with no close characterised
              relative.
            </p>
          )}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] text-left text-xs">
              <thead>
                <tr className="text-muted">
                  <th className="py-1.5 pr-3 font-medium">Rule</th>
                  <th className="py-1.5 pr-3 font-medium">Result</th>
                  <th className="py-1.5 pr-3 font-medium">Condition</th>
                  <th className="py-1.5 font-medium">Meaning</th>
                </tr>
              </thead>
              <tbody>
                {r.rules.map((x) => (
                  <tr key={x.id} className="border-t border-line/40 align-top">
                    <td className="py-1.5 pr-3 font-mono">{x.id}</td>
                    <td className="py-1.5 pr-3">
                      <AssessmentBadge category={x.category} short />
                    </td>
                    <td className="py-1.5 pr-3 text-ink/85">{x.condition}</td>
                    <td className="py-1.5 text-muted">{x.meaning}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="list-disc pl-5 text-xs text-muted">
            {r.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </div>
      )}
    </details>
  );
}

function fmtCounts(c: Partial<Record<AssessmentCategory, number>>) {
  return (["green", "yellow", "red", "insufficient"] as const).map((k) => `${c[k] ?? 0} ${k}`).join(", ");
}
