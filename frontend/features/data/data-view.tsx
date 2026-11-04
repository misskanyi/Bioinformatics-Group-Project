"use client";

import { ArrowRight, Microscope, Share2, Sigma, Thermometer } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ErrorState, Notice, Panel, PanelHeader, Skeleton } from "@/components/ui/primitives";
import { axisProps, ChartTooltip, gridProps } from "@/components/viz/chart-kit";
import { ConditionsView } from "@/features/conditions/conditions-view";
import { ClusterCharts } from "@/features/networks/cluster-charts";
import { NetworksView } from "@/features/networks/networks-view";
import { OrganismsView } from "@/features/organisms/organisms-view";
import { DatasetsView } from "@/features/datasets/datasets-view";
import { useApi } from "@/lib/api";
import { DATA_SECTIONS, type DataSection } from "@/lib/nav";
import { clusterColor } from "@/lib/palette";
import { cn, num } from "@/lib/utils";
import type { Audit, Clustering, Modelling, NetworkData, Overview } from "@/types/api";

/* ------------------------------------------------------------------ section nav */

function SectionNav({ active, onSelect }: { active: DataSection; onSelect: (s: DataSection) => void }) {
  return (
    <nav aria-label="Page sections" className="sticky top-16 z-10 -mx-4 overflow-x-auto border-b border-line/60 bg-void/80 px-4 py-2 backdrop-blur-xl sm:-mx-6 sm:px-6">
      <div className="flex gap-1">
        {DATA_SECTIONS.map((s) => (
          <button
            key={s.id}
            onClick={() => onSelect(s.id)}
            aria-current={active === s.id ? "true" : undefined}
            className={cn(
              "whitespace-nowrap rounded-lg px-3 py-1.5 text-[13px] transition",
              active === s.id ? "bg-elevated text-teal shadow-[inset_0_0_0_1px_rgb(72_225_205/0.35)]" : "text-muted hover:bg-elevated/60 hover:text-ink",
            )}
          >
            {s.label}
          </button>
        ))}
      </div>
    </nav>
  );
}

function SectionIntro({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="max-w-3xl">
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{children}</p>
    </div>
  );
}

/* ------------------------------------------------------------------ cleaning summary */

function CleaningSummary() {
  const audit = useApi<Audit>("/audit");
  const model = useApi<Modelling>("/modelling");
  const overview = useApi<Overview>("/overview");
  const a = audit.data?.available ? audit.data : undefined;
  const m = model.data;

  if (audit.loading || model.loading) return <Skeleton label="Loading dataset audit" className="h-64 rounded-[14px]" />;

  const before = a?.pazy
    ? [
        { label: "PAZy PET assay rows", value: a.pazy.assay_rows },
        { label: "Proteins with a PET assay", value: a.pazy.proteins_with_positive },
      ]
    : [];
  const screen = a?.screen_labels;

  return (
    <Panel>
      <PanelHeader
        eyebrow="Before and after cleaning"
        title="What survived quality control"
        description="Counts are read from the dataset audit and the cleaned protein table; nothing here is re-derived in the browser."
      />
      <div className="grid gap-4 p-5 lg:grid-cols-3">
        <div className="rounded-xl border border-line/70 bg-void/40 p-4">
          <div className="eyebrow mb-3 text-cyan">Before · as downloaded</div>
          <dl className="flex flex-col gap-2 text-sm">
            {before.length ? (
              before.map((r) => (
                <div key={r.label} className="flex justify-between gap-3">
                  <dt className="text-muted">{r.label}</dt>
                  <dd className="tabular font-mono">{num(r.value)}</dd>
                </div>
              ))
            ) : (
              <p className="text-[13px] text-muted">Audit statistics not generated.</p>
            )}
            {screen && (
              <>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted">Screening library sequences</dt>
                  <dd className="tabular font-mono">{num(screen.library_size_total)}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted">Screening enzymes assayed</dt>
                  <dd className="tabular font-mono">{num(screen.n_enzymes_assayed)}</dd>
                </div>
              </>
            )}
          </dl>
        </div>

        <div className="relative rounded-xl border border-line/70 bg-void/40 p-4">
          <div className="eyebrow mb-3 text-amber">Removed or set aside</div>
          <ul className="flex flex-col gap-2 text-[13px] leading-relaxed text-muted">
            <li>Assays on polymers other than PET, and assay records whose outcome could not be classified.</li>
            <li>Proteins with no valid sequence, or sequences containing non-standard amino-acid letters.</li>
            <li>Duplicate records, resolved so that each unique sequence appears once.</li>
            {screen && <li>{num(screen.never_positive_with_lt8_conditions)} screening enzymes with no detected product but fewer than eight conditions tested — held as uncertain, never used as negatives.</li>}
            <li>Computational ΔΔG prediction sheets inside the PETML workbooks, which are not measurements.</li>
          </ul>
        </div>

        <div className="rounded-xl border border-teal/30 bg-teal/[0.05] p-4">
          <div className="eyebrow mb-3 text-teal">After · used in this project</div>
          <dl className="flex flex-col gap-2 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-muted">Curated PET-active proteins</dt>
              <dd className="tabular font-mono text-teal">{overview.data ? num(overview.data.stats.proteins) : "—"}</dd>
            </div>
            {screen && (
              <>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted">Screen positives (≥ 1 condition)</dt>
                  <dd className="tabular font-mono text-teal">{num(screen.ever_positive)}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted">Condition-qualified negatives</dt>
                  <dd className="tabular font-mono text-rose">{num(screen.never_positive_with_ge8_conditions)}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted">Never assayed (prediction targets)</dt>
                  <dd className="tabular font-mono text-muted">{num(screen.library_never_assayed)}</dd>
                </div>
              </>
            )}
            {m?.dataset && (
              <div className="flex justify-between gap-3 border-t border-line/60 pt-2">
                <dt className="text-muted">Labelled for modelling</dt>
                <dd className="tabular font-mono text-mint">{num(m.dataset.n_proteins)}</dd>
              </div>
            )}
          </dl>
        </div>
      </div>
      <div className="px-5 pb-5">
        <Notice tone="warn">
          A zero measurement means the reported method detected no product <b>under that condition</b>. The curated PAZy set contains no protein whose PET
          measurements are all zero, so it supplies no protein-level negative class — this is the single biggest constraint on the machine learning.
        </Notice>
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ label composition */

function LabelComposition() {
  const audit = useApi<Audit>("/audit");
  const a = audit.data?.available ? audit.data : undefined;
  if (!a?.condition_labels) return null;
  const rows = a.condition_labels
    .map((c) => {
      const [substrate, temp, ph] = c.cond.split("|");
      return { ...c, label: `${substrate} ${temp}°C pH${ph}`, substrate };
    })
    .sort((x, y) => y.pos_rate - x.pos_rate);

  return (
    <Panel>
      <PanelHeader
        eyebrow="Activity by experimental condition"
        title="The same enzymes, twenty different answers"
        description="Share of assayed enzymes with detected product in each condition of the 2025 standardised screen (crystalline powder vs amorphous film, 40 vs 60 °C, pH 4.5–8.5). Activity is only meaningful with its condition attached."
      />
      <div className="p-5">
        <div className="h-[420px]">
          <ResponsiveContainer>
            <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 24, bottom: 4, left: 92 }}>
              <CartesianGrid {...gridProps} horizontal={false} />
              <XAxis type="number" domain={[0, 1]} tickFormatter={(t) => `${Math.round(t * 100)}%`} {...axisProps} />
              <YAxis type="category" dataKey="label" width={92} {...axisProps} />
              <Tooltip
                cursor={{ fill: "rgb(72 225 205 / 0.06)" }}
                content={({ payload }) => {
                  const r = payload?.[0]?.payload as (typeof rows)[number] | undefined;
                  return r ? (
                    <ChartTooltip
                      title={r.label}
                      rows={[
                        { label: "Detected", value: r.pos, color: "#69E8C3" },
                        { label: "Not detected", value: r.zero, color: "#EF8A9A" },
                        { label: "Enzymes tested", value: r.n },
                        { label: "Positive rate", value: `${Math.round(r.pos_rate * 100)}%` },
                      ]}
                    />
                  ) : null;
                }}
              />
              <Bar dataKey="pos_rate" radius={[0, 4, 4, 0]} isAnimationActive={false}>
                {rows.map((r) => (
                  <Cell key={r.cond} fill={r.substrate === "cryPow" ? "#48E1CD" : "#B49CF5"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted">
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm bg-teal" /> Crystalline PET powder
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm bg-violet" /> Amorphous PET film
          </span>
        </div>
        <p className="mt-3 max-w-3xl text-xs leading-relaxed text-muted">
          Only the crystalline-powder conditions at 40 °C are near balanced (47–54% positive), which is why modelling uses a condition-specific label rather
          than a global “PET-degrader” label.
        </p>
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ length distribution */

function LengthDistribution() {
  const net = useApi<NetworkData>("/network?min_identity=0.4&min_coverage=0.7");
  const bins = useMemo(() => {
    if (!net.data) return [];
    const width = 50;
    const counts = new Map<number, { total: number; byGroup: Record<string, number> }>();
    for (const n of net.data.nodes) {
      const b = Math.floor(n.length / width) * width;
      const entry = counts.get(b) ?? { total: 0, byGroup: {} };
      entry.total += 1;
      entry.byGroup[n.subcluster] = (entry.byGroup[n.subcluster] ?? 0) + 1;
      counts.set(b, entry);
    }
    return [...counts.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([bin, v]) => ({ bin, label: `${bin}–${bin + width - 1}`, ...v }));
  }, [net.data]);

  if (net.error)
    return (
      <Panel>
        <ErrorState message={net.error.message} onRetry={net.retry} />
      </Panel>
    );

  const lengths = net.data?.nodes.map((n) => n.length) ?? [];
  const median = lengths.length ? [...lengths].sort((a, b) => a - b)[Math.floor(lengths.length / 2)] : null;

  return (
    <Panel>
      <PanelHeader
        eyebrow="Exploratory analysis"
        title="Protein sequence length distribution"
        description={`All ${net.data ? num(net.data.nodes.length) : ""} curated PET-active proteins, in 50-residue bins.`.replace("  ", " ")}
      />
      <div className="p-5">
        {!net.data ? (
          <Skeleton label="Loading sequence length distribution" className="h-[280px]" />
        ) : (
          <>
            <div className="h-[280px]">
              <ResponsiveContainer>
                <BarChart data={bins} margin={{ top: 8, right: 8, bottom: 20, left: -12 }}>
                  <CartesianGrid {...gridProps} vertical={false} />
                  <XAxis dataKey="label" {...axisProps} interval={1} angle={-30} textAnchor="end" height={48} />
                  <YAxis {...axisProps} allowDecimals={false} />
                  <Tooltip
                    cursor={{ fill: "rgb(72 225 205 / 0.06)" }}
                    content={({ payload }) => {
                      const r = payload?.[0]?.payload as (typeof bins)[number] | undefined;
                      return r ? (
                        <ChartTooltip
                          title={`${r.label} residues`}
                          rows={[
                            { label: "Proteins", value: r.total },
                            ...Object.entries(r.byGroup)
                              .sort((a, b) => b[1] - a[1])
                              .map(([g, n]) => ({ label: g, value: n, color: clusterColor(g) })),
                          ]}
                        />
                      ) : null;
                    }}
                  />
                  <Bar dataKey="total" fill="#48E1CD" radius={[3, 3, 0, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-muted">
              Median length {median} aa. The long tail comes from subgroup G1b, whose members carry extra binding domains on top of the catalytic core.
            </p>
          </>
        )}
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ sections */

function Acquisition() {
  return (
    <div className="flex flex-col gap-6">
      <SectionIntro title="Data acquisition, preprocessing and quality control">
        Where every record came from, what was removed on the way in, and which checks the cleaned set passes. The pipeline writes each stage to a CSV, so any
        number shown here can be traced back to a file and, through it, to a published assay.
      </SectionIntro>
      <CleaningSummary />
      <DatasetsView />
    </div>
  );
}

function Exploration() {
  const clustering = useApi<Clustering>("/clustering");
  return (
    <div className="flex flex-col gap-6">
      <SectionIntro title="Exploratory data analysis, sequence analysis and clustering">
        Pairwise local alignment of every protein against every other gives a sequence-distance matrix. Clustering that matrix groups the proteins into
        families; projecting it (MDS) or the feature table (PCA) shows the same structure in two dimensions. Amino-acid composition is shown alongside, because
        composition alone turns out not to recover the families.
      </SectionIntro>
      <LengthDistribution />
      {clustering.error ? (
        <Panel>
          <ErrorState message={clustering.error.message} onRetry={clustering.retry} />
        </Panel>
      ) : clustering.data ? (
        <ClusterCharts data={clustering.data} />
      ) : (
        <Skeleton label="Loading clustering results" className="h-[520px] rounded-[14px]" />
      )}
      <LabelComposition />
    </div>
  );
}

function NetworkSection() {
  return (
    <div className="flex flex-col gap-6">
      <SectionIntro title="Protein sequence-similarity network">
        Each node is one curated PET-active protein and each edge joins two proteins whose sequences align above the identity and coverage thresholds. Hubs are
        proteins with many close relatives; bridges connect otherwise separate families.
      </SectionIntro>
      <NetworksView showClusterAnalysis={false} />
    </div>
  );
}

function ConditionsSection() {
  return (
    <div className="flex flex-col gap-6">
      <SectionIntro title="Reported assay conditions and outcomes">
        Every published PET assay for these proteins, with its temperature, pH, substrate form, detection method and outcome. Conditions differ between papers,
        so values are never pooled across studies and no temperature optimum is claimed.
      </SectionIntro>
      <ConditionsView />
    </div>
  );
}

function OrganismsSection() {
  return (
    <div className="flex flex-col gap-6">
      <SectionIntro title="Documented source organisms">
        An organism is attached to a protein only through a database record carrying the identical sequence, or a precursor/mature form of it. A similar
        sequence never assigns an organism.
      </SectionIntro>
      <OrganismsView />
    </div>
  );
}

const SECTION_ICON: Record<DataSection, typeof Sigma> = {
  acquisition: Sigma,
  exploration: Sigma,
  network: Share2,
  conditions: Thermometer,
  organisms: Microscope,
};

export function DataView() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const raw = params.get("section");
  const active = (DATA_SECTIONS.find((s) => s.id === raw)?.id ?? "acquisition") as DataSection;

  const go = (section: DataSection) => {
    const sp = new URLSearchParams(params.toString());
    sp.set("section", section);
    if (section !== "network") sp.delete("protein");
    router.replace(`${pathname}?${sp}`, { scroll: false });
  };

  const index = DATA_SECTIONS.findIndex((s) => s.id === active);
  const next = DATA_SECTIONS[index + 1];
  const Icon = SECTION_ICON[active];

  return (
    <div className="flex flex-col gap-6">
      <SectionNav active={active} onSelect={go} />

      <div className="flex items-center gap-2 text-muted">
        <Icon className="size-4" />
        <span className="eyebrow">
          Step {index + 1} of {DATA_SECTIONS.length}
        </span>
      </div>

      {active === "acquisition" && <Acquisition />}
      {active === "exploration" && <Exploration />}
      {active === "network" && <NetworkSection />}
      {active === "conditions" && <ConditionsSection />}
      {active === "organisms" && <OrganismsSection />}

      {next && (
        <button
          onClick={() => go(next.id)}
          className="group flex items-center justify-between gap-3 rounded-xl border border-line/70 bg-void/40 p-4 text-left transition hover:border-teal/50 hover:bg-elevated/50"
        >
          <span>
            <span className="eyebrow block">Next section</span>
            <span className="mt-1 block font-medium">{next.label}</span>
          </span>
          <ArrowRight className="size-5 text-muted transition group-hover:translate-x-1 group-hover:text-teal" />
        </button>
      )}
    </div>
  );
}
