"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { InfoTip, Metric, Panel, PanelHeader } from "@/components/ui/primitives";
import { axisProps, ChartTooltip, gridProps } from "@/components/viz/chart-kit";
import { PredictionNotice } from "@/features/discovery/evidence";
import { C } from "@/lib/palette";
import type { PredictionBlock, SequenceProfile } from "@/types/api";

import { residueColor, STANDARD_AA } from "./residues";

const PROPS: { key: keyof SequenceProfile["physicochemical"]; label: string; fmt: (v: number) => string; hint: string }[] = [
  { key: "molecular_weight_kda", label: "Molecular weight", fmt: (v) => `${v.toFixed(1)} kDa`, hint: "Average isotopic masses (ProtParam)." },
  { key: "isoelectric_point", label: "Isoelectric point", fmt: (v) => v.toFixed(2), hint: "pH at which the net charge is zero (ProtParam)." },
  { key: "gravy", label: "GRAVY", fmt: (v) => v.toFixed(3), hint: "Grand average of hydropathy (Kyte–Doolittle). Positive = hydrophobic overall." },
  { key: "instability_index", label: "Instability index", fmt: (v) => v.toFixed(1), hint: "Guruprasad et al. 1990. Above 40 predicts instability in vitro; a sequence-only estimate." },
  { key: "aromaticity", label: "Aromaticity", fmt: (v) => v.toFixed(3), hint: "Relative frequency of F, W and Y." },
];

/** Composition, physicochemical properties and motifs of the submitted protein (computed by pet_explorer.features). */
export function SequenceProfilePanel({ profile, prediction }: { profile: SequenceProfile; prediction: PredictionBlock }) {
  const comp = [...STANDARD_AA].map((aa) => ({ aa, pct: profile.composition[aa] ?? 0 }));
  const ss = profile.physicochemical;
  const m = profile.motifs;

  return (
    <Panel>
      <PanelHeader
        eyebrow="Sequence profile"
        title="Composition, properties and motifs"
        description="Computed from the sequence alone with the same functions used for the curated set. These describe the protein; they do not predict PET activity."
      />
      <div className="grid gap-6 p-5 xl:grid-cols-[1.15fr_1fr]">
        <div>
          <div className="eyebrow mb-2">Amino-acid composition (%)</div>
          <div className="h-[210px]">
            <ResponsiveContainer>
              <BarChart data={comp} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
                <CartesianGrid {...gridProps} vertical={false} />
                <XAxis dataKey="aa" {...axisProps} interval={0} />
                <YAxis {...axisProps} />
                <Tooltip
                  cursor={{ fill: "color-mix(in srgb, var(--color-electric) 8%, transparent)" }}
                  content={({ payload }) => {
                    const r = payload?.[0]?.payload as (typeof comp)[number] | undefined;
                    return r ? <ChartTooltip title={r.aa} rows={[{ label: "Share of residues", value: `${r.pct.toFixed(2)}%` }]} /> : null;
                  }}
                />
                <Bar dataKey="pct" radius={[3, 3, 0, 0]} isAnimationActive={false}>
                  {comp.map((r) => (
                    <Cell key={r.aa} fill={residueColor(r.aa) ?? C.muted} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="flex flex-col gap-5">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <Metric label="Length" value={`${profile.length} aa`} />
            {PROPS.map((p) => (
              <Metric key={p.key} label={p.label} value={p.fmt(ss[p.key])} accent={C.sky} hint={<InfoTip content={p.hint} />} />
            ))}
          </div>
          <div>
            <div className="eyebrow mb-2">Secondary-structure propensity</div>
            <div className="flex h-2.5 overflow-hidden rounded-full bg-line/50">
              <div style={{ width: `${100 * ss.helix_prone_fraction}%`, background: C.violet }} title="helix-prone" />
              <div style={{ width: `${100 * ss.turn_prone_fraction}%`, background: C.amber }} title="turn-prone" />
              <div style={{ width: `${100 * ss.sheet_prone_fraction}%`, background: C.aqua }} title="sheet-prone" />
            </div>
            <p className="mt-1.5 font-mono text-[11px] text-muted">
              helix {ss.helix_prone_fraction.toFixed(2)} · turn {ss.turn_prone_fraction.toFixed(2)} · sheet {ss.sheet_prone_fraction.toFixed(2)} (residue-class
              fractions, not a structure prediction; classes overlap)
            </p>
          </div>
        </div>

        <div className="rounded-xl border border-line/70 bg-void/40 p-4">
          <div className="eyebrow mb-2">Motif search · {m.name}</div>
          {m.count ? (
            <>
              <p className="text-[13px] text-ink/90">
                {m.count} occurrence{m.count === 1 ? "" : "s"}: {m.variants.join(", ")}
              </p>
              <div className="relative mt-3 h-3 rounded-full bg-line/50" aria-label="Motif positions along the sequence">
                {m.positions.map((p) => (
                  <span
                    key={p}
                    title={`position ${p}`}
                    className="absolute top-1/2 h-4 w-1 -translate-y-1/2 rounded bg-cyan shadow-[0_0_8px_var(--color-cyan)]"
                    style={{ left: `${(100 * (p - 1)) / profile.length}%` }}
                  />
                ))}
              </div>
              <div className="mt-1 flex justify-between font-mono text-[10px] text-muted">
                <span>1</span>
                <span>positions {m.positions.join(", ")}</span>
                <span>{profile.length}</span>
              </div>
            </>
          ) : (
            <p className="text-[13px] text-muted">
              Not found. 296 of 298 curated PET-active proteins carry it, so its absence is a warning sign, not a disqualification.
            </p>
          )}
        </div>

        <PredictionNotice prediction={prediction} />
      </div>
    </Panel>
  );
}
