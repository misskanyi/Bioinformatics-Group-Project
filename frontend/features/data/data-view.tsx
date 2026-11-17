"use client";

import { ArrowRight, Microscope, Share2, Sigma, Thermometer } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ErrorState, Notice, Panel, PanelHeader, Select, Skeleton } from "@/components/ui/primitives";
import {
  axisLabel,
  axisProps,
  barCursor,
  ChartControls,
  ChartInView,
  ChartTooltip,
  gridProps,
  Legend,
  Segmented,
  Takeaway,
  useChartMotion,
} from "@/components/viz/chart-kit";
import { ConditionsView } from "@/features/conditions/conditions-view";
import { ClusterCharts } from "@/features/networks/cluster-charts";
import { NetworksView } from "@/features/networks/networks-view";
import { OrganismsView } from "@/features/organisms/organisms-view";
import { DatasetsView } from "@/features/datasets/datasets-view";
import { useApi } from "@/lib/api";
import { DATA_SECTIONS, type DataSection } from "@/lib/nav";
import { C, clusterColor } from "@/lib/palette";
import { num, sortGroups } from "@/lib/utils";
import type { Audit, Clustering, Modelling, NetworkData, Overview } from "@/types/api";

/* ------------------------------------------------------------------ section intro */

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

const SUBSTRATE_LABEL: Record<string, string> = { cryPow: "Crystalline PET powder" };
const substrateLabel = (code: string) => SUBSTRATE_LABEL[code] ?? "Amorphous PET film";
const substrateColor = (code: string) => (code === "cryPow" ? C.aqua : C.violet);

function LabelComposition() {
  const audit = useApi<Audit>("/audit");
  const a = audit.data?.available ? audit.data : undefined;
  const [substrate, setSubstrate] = useState<string>("all");
  const [temp, setTemp] = useState<string>("all");
  const [sort, setSort] = useState<"rate" | "condition">("rate");

  const all = useMemo(
    () =>
      (a?.condition_labels ?? []).map((c) => {
        const [code, t, ph] = c.cond.split("|");
        return { ...c, label: `${code} ${t}°C pH${ph}`, substrate: code, temp: t, ph: Number(ph) };
      }),
    [a],
  );
  const substrates = useMemo(() => [...new Set(all.map((r) => r.substrate))], [all]);
  const temps = useMemo(() => [...new Set(all.map((r) => r.temp))].sort((x, y) => Number(x) - Number(y)), [all]);
  const rows = useMemo(() => {
    const r = all.filter((x) => (substrate === "all" || x.substrate === substrate) && (temp === "all" || x.temp === temp));
    return sort === "rate"
      ? r.sort((x, y) => y.pos_rate - x.pos_rate)
      : r.sort((x, y) => x.substrate.localeCompare(y.substrate) || Number(x.temp) - Number(y.temp) || x.ph - y.ph);
  }, [all, substrate, temp, sort]);
  const motion = useChartMotion(rows, 650);

  if (!a?.condition_labels) return null;
  const hi = rows.reduce((m, r) => (r.pos_rate > m.pos_rate ? r : m), rows[0]);
  const lo = rows.reduce((m, r) => (r.pos_rate < m.pos_rate ? r : m), rows[0]);
  const dirty = substrate !== "all" || temp !== "all" || sort !== "rate";

  return (
    <Panel>
      <PanelHeader
        eyebrow="Activity by experimental condition"
        title={`The same enzymes, ${all.length} different answers`}
        description="Share of assayed enzymes with detected product in each condition of the 2025 standardised screen (crystalline powder vs amorphous film, 40 vs 60 °C, pH 4.5–8.5). Activity is only meaningful with its condition attached."
      />
      <div className="p-5">
        <ChartControls
          dirty={dirty}
          onReset={() => {
            setSubstrate("all");
            setTemp("all");
            setSort("rate");
          }}
        >
          <Segmented
            label="Substrate"
            value={substrate}
            onChange={setSubstrate}
            options={[{ value: "all", label: "All" }, ...substrates.map((c) => ({ value: c, label: c === "cryPow" ? "Powder" : "Film" }))]}
          />
          <Segmented label="Temperature" value={temp} onChange={setTemp} options={[{ value: "all", label: "All" }, ...temps.map((t) => ({ value: t, label: `${t} °C` }))]} />
          <Segmented
            label="Sort"
            value={sort}
            onChange={setSort}
            options={[
              { value: "rate", label: "Positive rate" },
              { value: "condition", label: "Condition" },
            ]}
          />
        </ChartControls>
        <ChartInView className="chart-hl h-[420px]">
          <ResponsiveContainer>
            <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 24, bottom: 22, left: 92 }}>
              <CartesianGrid {...gridProps} horizontal={false} />
              <XAxis
                type="number"
                domain={[0, 1]}
                tickFormatter={(t) => `${Math.round(t * 100)}%`}
                {...axisProps}
                label={axisLabel("Enzymes with detected product (share of those assayed)")}
              />
              <YAxis type="category" dataKey="label" width={92} {...axisProps} />
              <Tooltip
                cursor={barCursor}
                content={({ payload }) => {
                  const r = payload?.[0]?.payload as (typeof rows)[number] | undefined;
                  return r ? (
                    <ChartTooltip
                      title={`${substrateLabel(r.substrate)} · ${r.temp} °C · pH ${r.ph}`}
                      rows={[
                        { label: "Detected", value: r.pos, color: C.mint },
                        { label: "Not detected", value: r.zero, color: C.rose },
                        { label: "Enzymes tested", value: r.n },
                        { label: "Positive rate", value: `${Math.round(r.pos_rate * 100)}%` },
                      ]}
                    />
                  ) : null;
                }}
              />
              <Bar dataKey="pos_rate" radius={[0, 4, 4, 0]} {...motion}>
                {rows.map((r) => (
                  <Cell key={r.cond} fill={substrateColor(r.substrate)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartInView>
        <Legend items={substrates.map((c) => ({ label: substrateLabel(c), color: substrateColor(c) }))} />
        {hi && lo && (
          <Takeaway>
            Across the {rows.length} condition{rows.length === 1 ? "" : "s"} shown, the positive rate ranges from {Math.round(lo.pos_rate * 100)}% (
            {substrateLabel(lo.substrate).toLowerCase()}, {lo.temp} °C, pH {lo.ph}) to {Math.round(hi.pos_rate * 100)}% ({substrateLabel(hi.substrate).toLowerCase()},{" "}
            {hi.temp} °C, pH {hi.ph}). Only the crystalline-powder conditions at 40 °C are near balanced, which is why modelling uses a condition-specific label
            rather than a global “PET-degrader” label.
          </Takeaway>
        )}
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ length distribution */

const BIN_WIDTHS = ["25", "50", "100"] as const;

function LengthDistribution() {
  const net = useApi<NetworkData>("/network?min_identity=0.4&min_coverage=0.7");
  const [width, setWidth] = useState<(typeof BIN_WIDTHS)[number]>("50");
  const [group, setGroup] = useState<string>("all");
  const groups = useMemo(() => sortGroups([...new Set(net.data?.nodes.map((n) => n.subcluster) ?? [])]), [net.data]);
  const nodes = useMemo(() => net.data?.nodes.filter((n) => group === "all" || n.subcluster === group) ?? [], [net.data, group]);

  // Bins span the full length range of all proteins, so filtering a subgroup keeps the x-axis fixed and bars morph in place.
  const bins = useMemo(() => {
    if (!net.data) return [];
    const w = Number(width);
    const lengths = net.data.nodes.map((n) => n.length);
    const lo = Math.floor(Math.min(...lengths) / w) * w;
    const hi = Math.floor(Math.max(...lengths) / w) * w;
    const out = new Map<number, { total: number; byGroup: Record<string, number> }>();
    for (let b = lo; b <= hi; b += w) out.set(b, { total: 0, byGroup: {} });
    for (const n of nodes) {
      const e = out.get(Math.floor(n.length / w) * w)!;
      e.total += 1;
      e.byGroup[n.subcluster] = (e.byGroup[n.subcluster] ?? 0) + 1;
    }
    return [...out.entries()].map(([bin, v]) => ({ bin, label: `${bin}–${bin + w - 1}`, ...v }));
  }, [net.data, nodes, width]);
  const motion = useChartMotion(bins, 650);

  if (net.error)
    return (
      <Panel>
        <ErrorState message={net.error.message} onRetry={net.retry} />
      </Panel>
    );

  const lengths = nodes.map((n) => n.length).sort((a, b) => a - b);
  const median = lengths.length ? lengths[Math.floor(lengths.length / 2)] : null;
  const medianBin = median != null ? bins.find((b) => median >= b.bin && median < b.bin + Number(width))?.label : undefined;
  const fill = group === "all" ? C.aqua : clusterColor(group);
  const longest = net.data && group === "all" ? [...net.data.nodes].sort((a, b) => b.length - a.length).slice(0, 10) : [];
  const longGroups = longest.reduce<Record<string, number>>((m, n) => ((m[n.subcluster] = (m[n.subcluster] ?? 0) + 1), m), {});
  const topLong = Object.entries(longGroups).sort((x, y) => y[1] - x[1])[0];

  return (
    <Panel>
      <PanelHeader
        eyebrow="Exploratory analysis"
        title="Protein sequence length distribution"
        description={`${net.data ? num(nodes.length) : "All"} curated PET-active protein${nodes.length === 1 ? "" : "s"}${group === "all" ? "" : ` in subgroup ${group}`}, counted in ${width}-residue bins.`}
      />
      <div className="p-5">
        {!net.data ? (
          <Skeleton label="Loading sequence length distribution" className="h-[280px]" />
        ) : (
          <>
            <ChartControls
              dirty={width !== "50" || group !== "all"}
              onReset={() => {
                setWidth("50");
                setGroup("all");
              }}
            >
              <Segmented label="Bin width" value={width} onChange={setWidth} options={BIN_WIDTHS.map((w) => ({ value: w, label: `${w} aa` }))} />
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted">Subgroup</span>
                <Select label="Subgroup" value={group} onChange={setGroup} options={[{ value: "all", label: "All proteins" }, ...groups.map((g) => ({ value: g, label: g }))]} />
              </div>
            </ChartControls>
            <ChartInView className="chart-hl h-[300px]">
              <ResponsiveContainer>
                <BarChart data={bins} margin={{ top: 16, right: 8, bottom: 30, left: 0 }}>
                  <CartesianGrid {...gridProps} vertical={false} />
                  <XAxis dataKey="label" {...axisProps} interval="preserveStartEnd" angle={-30} textAnchor="end" height={48} />
                  <YAxis {...axisProps} allowDecimals={false} width={52} label={axisLabel("Proteins", "insideLeft")} />
                  {medianBin && (
                    <ReferenceLine
                      x={medianBin}
                      stroke={C.amber}
                      strokeDasharray="4 4"
                      label={{ value: `median ${median} aa`, fill: C.amber, fontSize: 10, position: "top" }}
                    />
                  )}
                  <Tooltip
                    cursor={barCursor}
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
                  <Bar dataKey="total" fill={fill} radius={[3, 3, 0, 0]} {...motion} />
                </BarChart>
              </ResponsiveContainer>
            </ChartInView>
            <p className="-mt-1 text-center text-[11px] text-muted">Sequence length (amino-acid residues)</p>
            {median != null && (
              <Takeaway>
                Median length {median} aa{group === "all" ? "" : ` in subgroup ${group}`}, range {lengths[0]}–{lengths[lengths.length - 1]} aa.
                {topLong && ` ${topLong[1]} of the 10 longest proteins belong to subgroup ${topLong[0]}.`}
                {group === "all" && " The long tail is proteins carrying extra binding domains on top of the catalytic core; length on its own says nothing about PET activity."}
              </Takeaway>
            )}
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
    router.push(`${pathname}?${sp}`);
  };

  const index = DATA_SECTIONS.findIndex((s) => s.id === active);
  const next = DATA_SECTIONS[index + 1];
  const Icon = SECTION_ICON[active];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-2 text-muted">
        <Icon className="size-4" />
        <span className="eyebrow">
          Step {index + 1} of {DATA_SECTIONS.length}
        </span>
        <span className="text-[13px] text-ink/85">· {DATA_SECTIONS[index].label}</span>
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
