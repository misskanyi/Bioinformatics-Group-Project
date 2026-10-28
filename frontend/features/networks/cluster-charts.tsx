"use client";

import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";

import { Badge, InfoTip, Panel, PanelHeader, Select, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/primitives";
import { axisProps, ChartTooltip, gridProps, Legend } from "@/components/viz/chart-kit";
import { IdentityHeatmap } from "@/components/viz/identity-heatmap";
import { clusterColor } from "@/lib/palette";
import type { Clustering } from "@/types/api";

type Pt = { id: number; name: string; subcluster: string; x: number; y: number };

function Projection({ data, mode }: { data: Clustering; mode: "pca" | "mds" }) {
  const groups = useMemo(() => {
    const out: Record<string, Pt[]> = {};
    for (const p of data.points) (out[p.subcluster] ??= []).push({ id: p.id, name: p.name, subcluster: p.subcluster, x: p[mode][0], y: p[mode][1] });
    return out;
  }, [data, mode]);
  const v = mode === "pca" ? data.pca_variance : data.mds_variance;
  return (
    <div>
      <div className="h-[380px]">
        <ResponsiveContainer>
          <ScatterChart margin={{ top: 10, right: 16, bottom: 28, left: 4 }}>
            <CartesianGrid {...gridProps} />
            <XAxis type="number" dataKey="x" name="axis 1" {...axisProps} tickFormatter={(t) => Number(t).toFixed(mode === "pca" ? 0 : 2)}
              label={{ value: `${mode === "pca" ? "PC1" : "MDS axis 1"} (${(v[0] * 100).toFixed(0)}% of variance)`, position: "bottom", fill: "#9BB3C6", fontSize: 11 }} />
            <YAxis type="number" dataKey="y" name="axis 2" {...axisProps} tickFormatter={(t) => Number(t).toFixed(mode === "pca" ? 0 : 2)}
              label={{ value: `${mode === "pca" ? "PC2" : "MDS 2"} (${(v[1] * 100).toFixed(0)}%)`, angle: -90, position: "insideLeft", fill: "#9BB3C6", fontSize: 11 }} />
            <ZAxis range={[28, 28]} />
            <Tooltip
              cursor={{ stroke: "#294157" }}
              content={({ payload }) => {
                const p = payload?.[0]?.payload as Pt | undefined;
                return p ? <ChartTooltip title={p.name} rows={[{ label: "Subgroup", value: p.subcluster, color: clusterColor(p.subcluster) }, { label: "ID", value: p.id }]} /> : null;
              }}
            />
            {data.subclusters.map((s) => (
              <Scatter key={s} name={s} data={groups[s]} fill={clusterColor(s)} fillOpacity={0.8} isAnimationActive={false} />
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <Legend items={data.subclusters.map((s) => ({ label: s, color: clusterColor(s) }))} />
      <p className="mt-3 text-xs leading-relaxed text-muted">
        {mode === "pca"
          ? "PCA of standardised amino-acid composition and physicochemical features (length, pI, GRAVY, aromaticity …). Colours are the alignment-based clusters, so overlap here shows composition alone does not separate the families."
          : "Classical multidimensional scaling of alignment distances (1 − identity): the 2-D map that best preserves pairwise sequence distances. The two axes capture only part of the variance."}
      </p>
    </div>
  );
}

function Sizes({ data }: { data: Clustering }) {
  const rows = data.summary.map((s) => ({ ...s, label: s.subcluster }));
  return (
    <div>
      <div className="h-[300px]">
        <ResponsiveContainer>
          <BarChart data={rows} margin={{ top: 16, right: 8, bottom: 4, left: -12 }}>
            <CartesianGrid {...gridProps} vertical={false} />
            <XAxis dataKey="label" {...axisProps} />
            <YAxis {...axisProps} allowDecimals={false} />
            <Tooltip
              cursor={{ fill: "rgb(72 225 205 / 0.06)" }}
              content={({ payload }) => {
                const r = payload?.[0]?.payload as (typeof rows)[number] | undefined;
                return r ? (
                  <ChartTooltip
                    title={`Subgroup ${r.subcluster}`}
                    rows={[
                      { label: "Proteins", value: r.n_proteins, color: clusterColor(r.subcluster) },
                      { label: "Median length", value: `${r.median_length} aa` },
                      { label: "Mean within identity", value: r.mean_within_identity_pct == null ? "—" : `${r.mean_within_identity_pct}%` },
                      { label: "Publications", value: r.n_publications },
                    ]}
                  />
                ) : null;
              }}
            />
            <Bar dataKey="n_proteins" radius={[4, 4, 0, 0]} label={{ position: "top", fill: "#F0F8FF", fontSize: 11 }}>
              {rows.map((r) => (
                <Cell key={r.subcluster} fill={clusterColor(r.subcluster)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
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
              <tr key={s.subcluster} className="border-b border-line/40 align-top">
                <td className="px-2 py-2 font-mono" style={{ color: clusterColor(s.subcluster) }}>
                  {s.subcluster}
                </td>
                <td className="tabular px-2 py-2">{s.n_proteins}</td>
                <td className="tabular px-2 py-2">
                  {s.median_length} ({s.length_range})
                </td>
                <td className="tabular px-2 py-2">{s.mean_within_identity_pct == null ? "—" : `${s.mean_within_identity_pct}%`}</td>
                <td className="px-2 py-2">
                  <Badge color={s.coherence.startsWith("coherent") ? "#69E8C3" : s.coherence.startsWith("moderate") ? "#4CA8D8" : "#E8B56B"} dot={false}>
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
    </div>
  );
}

function Composition({ data }: { data: Clustering }) {
  const [group, setGroup] = useState(data.subclusters[1] ?? data.subclusters[0]);
  const rows = data.composition.map((c) => ({ aa: c.aa, all: c.all as number, group: c[group] as number }));
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <span className="text-xs text-muted">Compare subgroup</span>
        <Select label="Subgroup" value={group} onChange={setGroup} options={data.subclusters.map((s) => ({ value: s, label: s }))} />
        <span className="text-xs text-muted">with the mean of all 298 proteins</span>
      </div>
      <div className="h-[320px]">
        <ResponsiveContainer>
          <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 4, left: -12 }} barGap={1}>
            <CartesianGrid {...gridProps} vertical={false} />
            <XAxis dataKey="aa" {...axisProps} interval={0} />
            <YAxis {...axisProps} unit="%" />
            <Tooltip
              cursor={{ fill: "rgb(72 225 205 / 0.06)" }}
              content={({ payload, label }) =>
                payload?.length ? (
                  <ChartTooltip
                    title={`Residue ${label}`}
                    rows={[
                      { label: group, value: `${(payload[1]?.value as number)?.toFixed(2)}%`, color: clusterColor(group) },
                      { label: "All proteins", value: `${(payload[0]?.value as number)?.toFixed(2)}%`, color: "#5F7A90" },
                    ]}
                  />
                ) : null
              }
            />
            <Bar dataKey="all" fill="#5F7A90" radius={[3, 3, 0, 0]} />
            <Bar dataKey="group" fill={clusterColor(group)} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <Legend items={[{ label: "All proteins (mean)", color: "#5F7A90" }, { label: `Subgroup ${group} (mean)`, color: clusterColor(group) }]} />
    </div>
  );
}

export function ClusterCharts({ data }: { data: Clustering }) {
  const sel = data.selection;
  return (
    <Panel>
      <PanelHeader
        eyebrow="Clustering analysis"
        title="How the 298 proteins group"
        description={
          <>
            Final clusters: average-linkage hierarchical clustering of alignment distances, {sel.selected_row.n_clusters} clusters (silhouette{" "}
            {sel.selected_row.silhouette_alignment.toFixed(2)}, bootstrap stability ARI {sel.selected_row.stability_ari_mean.toFixed(2)}). The dominant
            cluster G1 is split into subgroups G1a / G1b by k-means on the alignment map.
          </>
        }
        action={<InfoTip content="Method chosen by comparing hierarchical, k-means and DBSCAN variants on silhouette, bootstrap stability and within-cluster identity (outputs/explorer/clustering/method_comparison.csv)." />}
      />
      <div className="p-5">
        <Tabs defaultValue="mds">
          <TabsList>
            <TabsTrigger value="mds">Alignment map (MDS)</TabsTrigger>
            <TabsTrigger value="pca">Feature PCA</TabsTrigger>
            <TabsTrigger value="sizes">Cluster sizes</TabsTrigger>
            <TabsTrigger value="composition">Amino-acid composition</TabsTrigger>
            <TabsTrigger value="heatmap">Identity heatmap</TabsTrigger>
          </TabsList>
          <div className="mt-5">
            <TabsContent value="mds">
              <Projection data={data} mode="mds" />
            </TabsContent>
            <TabsContent value="pca">
              <Projection data={data} mode="pca" />
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
