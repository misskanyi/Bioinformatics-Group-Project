"use client";

import { ArrowUpRight, Share2, X } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Badge, InfoTip, Panel, PanelHeader, Select, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/primitives";
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
import { IdentityHeatmap } from "@/components/viz/identity-heatmap";
import { ScatterPlot, type ScatterPoint } from "@/components/viz/scatter-plot";
import { useApi } from "@/lib/api";
import { networkHref, sequenceHref } from "@/lib/nav";
import { C, clusterColor, ORGANISM_EVIDENCE } from "@/lib/palette";
import { num } from "@/lib/utils";
import type { Clustering, NetworkData, NetworkNode, OrganismEvidence } from "@/types/api";

// Same request as the length histogram and the network section, so it is served from the session cache.
const NETWORK_PATH = "/network?min_identity=0.4&min_coverage=0.7";

type Mode = "mds" | "pca";
type ColorBy = "subgroup" | "organism";

const ORGANISM_ORDER: OrganismEvidence[] = ["exact_sequence", "contained_sequence", "pazy_curation_text", "none"];

/* ------------------------------------------------------------------ projection */

function Inspector({
  p,
  node,
  mode,
  onClose,
}: {
  p: Clustering["points"][number];
  node?: NetworkNode;
  mode: Mode;
  onClose: () => void;
}) {
  const ev = node?.organism_evidence ? ORGANISM_EVIDENCE[node.organism_evidence] : undefined;
  return (
    <div className="reveal flex h-full flex-col gap-3 rounded-xl border border-line/70 bg-void/40 p-4 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="eyebrow mb-1">Selected protein</div>
          <div className="break-words font-medium leading-snug text-ink">{p.name}</div>
        </div>
        <button type="button" onClick={onClose} aria-label="Clear selection" className="rounded p-0.5 text-muted transition hover:text-ink">
          <X className="size-4" />
        </button>
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-[13px]">
        <dt className="text-muted">Subgroup</dt>
        <dd>
          <Badge color={clusterColor(p.subcluster)}>{p.subcluster}</Badge>
        </dd>
        <dt className="text-muted">Protein ID</dt>
        <dd className="tabular font-mono">{p.id}</dd>
        {node && (
          <>
            <dt className="text-muted">Length</dt>
            <dd className="tabular font-mono">{num(node.length)} aa</dd>
            <dt className="text-muted">Network relatives</dt>
            <dd className="tabular font-mono">{node.degree}</dd>
            <dt className="text-muted">Assay temperatures</dt>
            <dd className="tabular font-mono">{node.n_temperatures}</dd>
            <dt className="col-span-2 mt-1 text-muted">Organism</dt>
            <dd className="col-span-2 -mt-1 min-w-0">
              <span className="italic">{node.organism ?? "Unknown"}</span>
              {ev && (
                <span className="mt-0.5 block text-[11px]" style={{ color: ev.color }}>
                  {ev.short}
                </span>
              )}
            </dd>
          </>
        )}
        <dt className="text-muted">{mode === "pca" ? "PC1, PC2" : "MDS 1, 2"}</dt>
        <dd className="tabular font-mono text-muted">
          {p[mode][0].toFixed(mode === "pca" ? 2 : 3)}, {p[mode][1].toFixed(mode === "pca" ? 2 : 3)}
        </dd>
      </dl>
      <div className="mt-auto flex flex-col gap-1.5 border-t border-line/60 pt-3 text-[13px]">
        <Link href={networkHref(p.id)} className="inline-flex items-center gap-1.5 text-cyan hover:underline">
          <Share2 className="size-3.5" /> Show in similarity network
        </Link>
        <Link href={sequenceHref(p.id)} className="inline-flex items-center gap-1.5 text-cyan hover:underline">
          <ArrowUpRight className="size-3.5" /> Use as query in Discovery
        </Link>
      </div>
      <p className="text-[11px] leading-snug text-muted">Position reflects similarity to other proteins only. It is not evidence of PET activity.</p>
    </div>
  );
}

function Projection({ data }: { data: Clustering }) {
  const net = useApi<NetworkData>(NETWORK_PATH);
  const nodes = useMemo(() => new Map(net.data?.nodes.map((n) => [n.id, n]) ?? []), [net.data]);
  const subOf = useMemo(() => new Map(data.points.map((p) => [p.id, p.subcluster])), [data]);

  const [mode, setMode] = useState<Mode>("mds");
  const [colorBy, setColorBy] = useState<ColorBy>("subgroup");
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [emphasis, setEmphasis] = useState<string | null>(null);
  const [selected, setSelected] = useState<number | null>(null);

  const colorOf = (g: string, by: ColorBy) => (by === "subgroup" ? clusterColor(g) : ORGANISM_EVIDENCE[g as OrganismEvidence].color);

  const points: ScatterPoint[] = useMemo(
    () =>
      data.points.map((p) => {
        const g = colorBy === "subgroup" ? p.subcluster : (nodes.get(p.id)?.organism_evidence ?? "none");
        return { id: p.id, x: p[mode][0], y: p[mode][1], group: g, color: colorOf(g, colorBy), label: p.name };
      }),
    [data, mode, colorBy, nodes],
  );

  const groups = colorBy === "subgroup" ? data.subclusters : ORGANISM_ORDER.filter((o) => points.some((p) => p.group === o));
  const counts = useMemo(() => {
    const m = new Map<string, number>();
    for (const p of points) m.set(p.group, (m.get(p.group) ?? 0) + 1);
    return m;
  }, [points]);

  const v = mode === "pca" ? data.pca_variance : data.mds_variance;
  const axis = (i: 0 | 1) => `${mode === "pca" ? `PC${i + 1}` : `MDS axis ${i + 1}`} (${(v[i] * 100).toFixed(0)}% of variance)`;
  const sel = selected != null ? data.points.find((p) => p.id === selected) : undefined;
  const dirty = mode !== "mds" || colorBy !== "subgroup" || hidden.size > 0 || selected != null;
  const groupLabel = (g: string) => (colorBy === "subgroup" ? g : ORGANISM_EVIDENCE[g as OrganismEvidence].short);

  const toggle = (g: string) =>
    setHidden((h) => {
      const n = new Set(h);
      if (n.has(g)) n.delete(g);
      else n.add(g);
      return n;
    });

  return (
    <div>
      <ChartControls
        dirty={dirty}
        onReset={() => {
          setMode("mds");
          setColorBy("subgroup");
          setHidden(new Set());
          setSelected(null);
        }}
      >
        <Segmented
          label="Projection"
          value={mode}
          onChange={setMode}
          options={[
            { value: "mds", label: "Sequence alignment (MDS)" },
            { value: "pca", label: "Feature space (PCA)" },
          ]}
        />
        {net.data && (
          <Segmented
            label="Colour by"
            value={colorBy}
            onChange={(c) => {
              setColorBy(c);
              setHidden(new Set());
            }}
            options={[
              { value: "subgroup", label: "Sequence subgroup" },
              { value: "organism", label: "Organism evidence" },
            ]}
          />
        )}
      </ChartControls>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div className="min-w-0">
          <ChartInView className="h-[400px]">
            <ScatterPlot
              points={points}
              xLabel={axis(0)}
              yLabel={axis(1)}
              hidden={hidden}
              emphasis={emphasis}
              selectedId={selected}
              onSelect={setSelected}
              ariaLabel={`${mode === "pca" ? "PCA of sequence features" : "MDS of alignment distances"} for ${data.points.length} proteins. Use arrow keys to step through proteins and Enter to inspect one.`}
              renderTooltip={(p) => {
                const node = nodes.get(p.id);
                return (
                  <ChartTooltip
                    title={p.label}
                    rows={[
                      { label: colorBy === "subgroup" ? "Subgroup" : "Organism evidence", value: groupLabel(p.group), color: p.color },
                      ...(colorBy === "organism" ? [{ label: "Subgroup", value: subOf.get(p.id) ?? "—" }] : []),
                      ...(node ? [{ label: "Length", value: `${node.length} aa` }] : []),
                    ]}
                    note="Click to inspect"
                  />
                );
              }}
            />
          </ChartInView>
          <Legend
            className="mt-2"
            items={groups.map((g) => ({ key: g, label: `${groupLabel(g)} (${counts.get(g) ?? 0})`, color: colorOf(g, colorBy) }))}
            hidden={hidden}
            onToggle={toggle}
            onHover={setEmphasis}
          />
          <p className="mt-1 text-[11px] text-muted">Hover a legend entry to highlight its group; click it to hide or show the group. With the chart focused, arrow keys step through proteins.</p>
        </div>
        {sel ? (
          <Inspector p={sel} node={nodes.get(sel.id)} mode={mode} onClose={() => setSelected(null)} />
        ) : (
          <div className="hidden flex-col justify-center gap-2 rounded-xl border border-dashed border-line/70 p-4 text-center text-[13px] text-muted lg:flex">
            <span className="font-medium text-ink">Inspect a protein</span>
            Click any point to see its subgroup, length, organism evidence and links to the network and sequence matcher.
          </div>
        )}
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-line/60 bg-void/30 p-3 text-xs leading-relaxed text-muted">
          <div className="mb-1.5 flex flex-wrap items-center gap-2">
            <Badge color={C.aqua} dot={false}>
              Sequence homology
            </Badge>
            <span className="text-ink/85">Alignment map (MDS)</span>
          </div>
          Classical multidimensional scaling of alignment distances (1 − identity): the 2-D map that best preserves pairwise sequence distances. The
          subgroups were defined on these distances, so they separate here largely by construction.
        </div>
        <div className="rounded-lg border border-line/60 bg-void/30 p-3 text-xs leading-relaxed text-muted">
          <div className="mb-1.5 flex flex-wrap items-center gap-2">
            <Badge color={C.violet} dot={false}>
              Feature space
            </Badge>
            <span className="text-ink/85">Feature PCA</span>
          </div>
          PCA of standardised amino-acid composition and physicochemical features (length, pI, GRAVY, aromaticity …). Colours are still the
          alignment-based subgroups, so overlap here shows composition alone does not separate the families.
        </div>
      </div>
      <Takeaway>
        {mode === "mds"
          ? `The two alignment axes capture ${(data.mds_variance[0] * 100).toFixed(0)}% and ${(data.mds_variance[1] * 100).toFixed(0)}% of the variance in pairwise sequence distance: nearby points are close relatives, but distances in the plane are approximate.`
          : `PC1 and PC2 explain ${(data.pca_variance[0] * 100).toFixed(0)}% and ${(data.pca_variance[1] * 100).toFixed(0)}% of the feature variance. Switch projections to watch each protein move: groups that are tight by alignment overlap in feature space.`}{" "}
        Neither map, nor the clusters, shows whether a protein degrades PET.
      </Takeaway>
    </div>
  );
}

/* ------------------------------------------------------------------ sizes */

function Sizes({ data }: { data: Clustering }) {
  const rows = useMemo(() => data.summary.map((s) => ({ ...s, label: s.subcluster })), [data]);
  const motion = useChartMotion(rows, 700);
  const [selected, setSelected] = useState<string | null>(null);
  const total = rows.reduce((a, r) => a + r.n_proteins, 0);
  const largest = [...rows].sort((a, b) => b.n_proteins - a.n_proteins)[0];
  const pick = (g: string | undefined) => setSelected((cur) => (g == null || cur === g ? null : g));

  return (
    <div>
      <ChartInView className="h-[300px]">
        <ResponsiveContainer>
          <BarChart
            data={rows}
            margin={{ top: 20, right: 8, bottom: 22, left: 0 }}
            onClick={(s) => {
              const i = s?.activeTooltipIndex;
              if (i != null) pick(rows[Number(i)]?.subcluster);
            }}
            className="cursor-pointer"
          >
            <CartesianGrid {...gridProps} vertical={false} />
            <XAxis dataKey="label" {...axisProps} label={axisLabel("Sequence subgroup")} />
            <YAxis {...axisProps} allowDecimals={false} label={axisLabel("Proteins", "insideLeft")} width={52} />
            <Tooltip
              cursor={barCursor}
              content={({ payload }) => {
                const r = payload?.[0]?.payload as (typeof rows)[number] | undefined;
                return r ? (
                  <ChartTooltip
                    title={`Subgroup ${r.subcluster}`}
                    rows={[
                      { label: "Proteins", value: r.n_proteins, color: clusterColor(r.subcluster) },
                      { label: "Share of set", value: `${((100 * r.n_proteins) / total).toFixed(1)}%` },
                      { label: "Median length", value: `${r.median_length} aa` },
                      { label: "Mean within identity", value: r.mean_within_identity_pct == null ? "—" : `${r.mean_within_identity_pct}%` },
                      { label: "Publications", value: r.n_publications },
                    ]}
                    note="Click to highlight in the table"
                  />
                ) : null;
              }}
            />
            <Bar dataKey="n_proteins" radius={[4, 4, 0, 0]} {...motion}>
              {rows.map((r) => (
                <Cell
                  key={r.subcluster}
                  fill={clusterColor(r.subcluster)}
                  fillOpacity={selected == null || selected === r.subcluster ? 1 : 0.3}
                  stroke={selected === r.subcluster ? C.ink : "none"}
                  strokeWidth={1.5}
                />
              ))}
              <LabelList dataKey="n_proteins" position="top" fill={C.ink} fontSize={11} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </ChartInView>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-xs">
          <thead>
            <tr className="text-muted">
              {["Subgroup", "Proteins", "Length (median, range)", "Within identity", "Coherence", "GxSxG motif", "Example members"].map((h) => (
                <th key={h} className="border-b border-line px-2 py-2 font-normal">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.summary.map((s) => (
              <tr
                key={s.subcluster}
                onClick={() => pick(s.subcluster)}
                className="cursor-pointer border-b border-line/40 align-top transition-[background-color,opacity] duration-200 hover:bg-elevated/40"
                style={{
                  background: selected === s.subcluster ? "color-mix(in srgb, var(--color-electric) 8%, transparent)" : undefined,
                  opacity: selected == null || selected === s.subcluster ? 1 : 0.55,
                }}
              >
                <td className="px-2 py-2 font-mono">
                  <button
                    type="button"
                    aria-pressed={selected === s.subcluster}
                    onClick={(e) => {
                      e.stopPropagation();
                      pick(s.subcluster);
                    }}
                    className="rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/50"
                    style={{ color: clusterColor(s.subcluster) }}
                  >
                    {s.subcluster}
                  </button>
                </td>
                <td className="tabular px-2 py-2">{s.n_proteins}</td>
                <td className="tabular px-2 py-2">
                  {s.median_length} ({s.length_range})
                </td>
                <td className="tabular px-2 py-2">{s.mean_within_identity_pct == null ? "—" : `${s.mean_within_identity_pct}%`}</td>
                <td className="px-2 py-2">
                  <Badge color={s.coherence.startsWith("coherent") ? C.mint : s.coherence.startsWith("moderate") ? C.sky : C.amber} dot={false}>
                    {s.coherence.split(" (")[0]}
                  </Badge>
                </td>
                <td className="px-2 py-2 font-mono text-muted">{s.with_gxsxg}</td>
                <td className="max-w-xs px-2 py-2 text-muted">{s.example_members}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {largest && (
        <Takeaway>
          Subgroup {largest.subcluster} holds {largest.n_proteins} of {total} proteins ({((100 * largest.n_proteins) / total).toFixed(0)}%), so the curated
          set is dominated by one sequence family; the smaller subgroups rest on few proteins and should be read with care.
        </Takeaway>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ composition */

type SortBy = "alpha" | "difference" | "abundance";

function Composition({ data }: { data: Clustering }) {
  const initial = data.subclusters[1] ?? data.subclusters[0];
  const [group, setGroup] = useState(initial);
  const [sort, setSort] = useState<SortBy>("alpha");
  const rows = useMemo(() => {
    const r = data.composition.map((c) => ({ aa: c.aa, all: c.all as number, group: c[group] as number, diff: (c[group] as number) - (c.all as number) }));
    if (sort === "difference") r.sort((a, b) => Math.abs(b.diff) - Math.abs(a.diff));
    else if (sort === "abundance") r.sort((a, b) => b.all - a.all);
    else r.sort((a, b) => a.aa.localeCompare(b.aa));
    return r;
  }, [data, group, sort]);
  const motion = useChartMotion(rows, 600);
  const byDiff = [...rows].sort((a, b) => b.diff - a.diff);
  const top = byDiff[0];
  const bottom = byDiff[byDiff.length - 1];

  return (
    <div>
      <ChartControls
        dirty={group !== initial || sort !== "alpha"}
        onReset={() => {
          setGroup(initial);
          setSort("alpha");
        }}
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted">Compare subgroup</span>
          <Select label="Subgroup" value={group} onChange={setGroup} options={data.subclusters.map((s) => ({ value: s, label: s }))} />
          <span className="text-xs text-muted">with the mean of all {data.points.length} proteins</span>
        </div>
        <Segmented
          label="Sort"
          value={sort}
          onChange={setSort}
          options={[
            { value: "alpha", label: "A–Z" },
            { value: "abundance", label: "Abundance" },
            { value: "difference", label: "Largest difference" },
          ]}
        />
      </ChartControls>
      <ChartInView className="chart-hl h-[320px]">
        <ResponsiveContainer>
          <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 22, left: 0 }} barGap={1}>
            <CartesianGrid {...gridProps} vertical={false} />
            <XAxis dataKey="aa" {...axisProps} interval={0} label={axisLabel("Amino acid (one-letter code)")} />
            <YAxis {...axisProps} unit="%" width={52} label={axisLabel("Mean composition", "insideLeft")} />
            <Tooltip
              cursor={barCursor}
              content={({ payload, label }) => {
                const r = payload?.[0]?.payload as (typeof rows)[number] | undefined;
                return r ? (
                  <ChartTooltip
                    title={`Residue ${label}`}
                    rows={[
                      { label: `Subgroup ${group}`, value: `${r.group.toFixed(2)}%`, color: clusterColor(group) },
                      { label: "All proteins", value: `${r.all.toFixed(2)}%`, color: C.slate },
                      { label: "Difference", value: `${r.diff >= 0 ? "+" : ""}${r.diff.toFixed(2)} pp` },
                    ]}
                  />
                ) : null;
              }}
            />
            <Bar dataKey="all" fill={C.slate} radius={[3, 3, 0, 0]} {...motion} />
            <Bar dataKey="group" fill={clusterColor(group)} radius={[3, 3, 0, 0]} {...motion} />
          </BarChart>
        </ResponsiveContainer>
      </ChartInView>
      <Legend items={[{ label: "All proteins (mean)", color: C.slate }, { label: `Subgroup ${group} (mean)`, color: clusterColor(group) }]} />
      {top && bottom && (
        <Takeaway>
          Compared with the whole set, subgroup {group} is most enriched in {top.aa} ({top.diff >= 0 ? "+" : ""}
          {top.diff.toFixed(1)} percentage points) and most depleted in {bottom.aa} ({bottom.diff.toFixed(1)} pp). Shifts of this size are modest, which fits
          the PCA view: composition alone does not recover the sequence families.
        </Takeaway>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ panel */

export function ClusterCharts({ data }: { data: Clustering }) {
  const sel = data.selection;
  return (
    <Panel>
      <PanelHeader
        eyebrow="Clustering analysis"
        title={`How the ${data.points.length} proteins group`}
        description={
          <>
            Final clusters: average-linkage hierarchical clustering of alignment distances, {sel.selected_row.n_clusters} clusters (silhouette{" "}
            {sel.selected_row.silhouette_alignment.toFixed(2)}, bootstrap stability ARI {sel.selected_row.stability_ari_mean.toFixed(2)}). The dominant
            cluster G1 is split into subgroups G1a / G1b by k-means on the alignment map. Clusters describe sequence similarity, not PET activity.
          </>
        }
        action={
          <InfoTip content="Method chosen by comparing hierarchical, k-means and DBSCAN variants on silhouette, bootstrap stability and within-cluster identity (outputs/explorer/clustering/method_comparison.csv). The API does not expose the linkage tree, so no dendrogram is drawn." />
        }
      />
      <div className="p-5">
        <Tabs defaultValue="projection">
          <TabsList>
            <TabsTrigger value="projection">Projection map</TabsTrigger>
            <TabsTrigger value="sizes">Cluster sizes</TabsTrigger>
            <TabsTrigger value="composition">Amino-acid composition</TabsTrigger>
            <TabsTrigger value="heatmap">Identity heatmap</TabsTrigger>
          </TabsList>
          <div className="mt-5">
            <TabsContent value="projection">
              <Projection data={data} />
            </TabsContent>
            <TabsContent value="sizes">
              <Sizes data={data} />
            </TabsContent>
            <TabsContent value="composition">
              <Composition data={data} />
            </TabsContent>
            <TabsContent value="heatmap">
              <IdentityHeatmap data={data.heatmap} />
            </TabsContent>
          </div>
        </Tabs>
      </div>
    </Panel>
  );
}
