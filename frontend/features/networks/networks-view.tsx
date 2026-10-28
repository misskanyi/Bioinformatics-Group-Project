"use client";

import { Download, Maximize2, RotateCcw, Search, ZoomIn, ZoomOut } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ErrorState, InfoTip, Input, Metric, Notice, Panel, PanelHeader, Skeleton, Slider, Tip } from "@/components/ui/primitives";
import { NetworkGraph, type NetworkGraphHandle } from "@/components/viz/network-graph";
import { useApi } from "@/lib/api";
import { clusterColor } from "@/lib/palette";
import { cn, num, sortGroups } from "@/lib/utils";
import type { Clustering, NetworkData } from "@/types/api";

import { ClusterCharts } from "./cluster-charts";
import { NodePanel } from "./node-panel";

const DEFAULT = { identity: 0.4, coverage: 0.7 };

function downloadCsv(name: string, rows: (string | number | null)[][]) {
  const csv = rows.map((r) => r.map((v) => (v == null ? "" : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : v)).join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  a.click();
  URL.revokeObjectURL(url);
}

export function NetworksView() {
  const params = useSearchParams();
  const router = useRouter();
  const graph = useRef<NetworkGraphHandle>(null);
  const [identity, setIdentity] = useState(DEFAULT.identity);
  const [coverage, setCoverage] = useState(DEFAULT.coverage);
  const [applied, setApplied] = useState(DEFAULT);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [notFound, setNotFound] = useState(false);
  const selected = params.get("protein") ? Number(params.get("protein")) : null;

  const net = useApi<NetworkData>(`/network?min_identity=${applied.identity}&min_coverage=${applied.coverage}`);
  const clustering = useApi<Clustering>("/clustering");
  const [shown, setShown] = useState<NetworkData>();
  useEffect(() => {
    if (net.data) setShown(net.data); // keep the previous graph visible while a new threshold loads
  }, [net.data]);

  const groups = useMemo(() => sortGroups([...new Set(shown?.nodes.map((n) => n.subcluster) ?? [])]), [shown]);
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    shown?.nodes.forEach((n) => (c[n.subcluster] = (c[n.subcluster] ?? 0) + 1));
    return c;
  }, [shown]);
  const node = shown?.nodes.find((n) => n.id === selected) ?? null;

  const select = (id: number | null) => {
    const sp = new URLSearchParams(params.toString());
    if (id == null) sp.delete("protein");
    else sp.set("protein", String(id));
    router.replace(`/networks${sp.size ? `?${sp}` : ""}`, { scroll: false });
  };

  useEffect(() => {
    if (selected != null && shown) setTimeout(() => graph.current?.focus(selected), 300);
  }, [selected, shown]);

  const search = (e: React.FormEvent) => {
    e.preventDefault();
    const q = query.trim().toLowerCase();
    if (!q || !shown) return;
    const hit = shown.nodes.find((n) => String(n.id) === q) ?? shown.nodes.find((n) => n.name.toLowerCase() === q) ?? shown.nodes.find((n) => n.name.toLowerCase().includes(q));
    setNotFound(!hit);
    if (hit) {
      if (hidden.has(hit.subcluster)) setHidden((h) => new Set([...h].filter((x) => x !== hit.subcluster)));
      select(hit.id);
    }
  };

  const reset = () => {
    setIdentity(DEFAULT.identity);
    setCoverage(DEFAULT.coverage);
    setApplied(DEFAULT);
    setHidden(new Set());
    setQuery("");
    select(null);
    setTimeout(() => graph.current?.fit(), 50);
  };

  const exportCurrent = () => {
    if (!shown) return;
    const names = new Map(shown.nodes.map((n) => [n.id, n.name]));
    downloadCsv(`ssn_edges_id${applied.identity}_cov${applied.coverage}.csv`, [
      ["source", "target", "source_name", "target_name", "interaction", "identity", "min_coverage"],
      ...shown.edges.map(([s, t, i, c]) => [s, t, names.get(s)!, names.get(t)!, "sequence_similarity", i, c]),
    ]);
  };

  return (
    <div className="flex flex-col gap-6">
      <Notice>
        This is a <b>protein sequence-similarity network</b>: an edge means two proteins have similar amino-acid sequences (local-alignment identity and coverage
        above the thresholds). It is <b>not</b> a protein–protein interaction network.
      </Notice>

      <div className="grid items-start gap-6 xl:grid-cols-[1fr_320px] 2xl:grid-cols-[1fr_360px]">
        <Panel className="flex min-w-0 flex-col overflow-hidden">
          {/* controls */}
          <div className="flex flex-wrap items-end gap-x-6 gap-y-4 border-b border-line/60 p-4">
            <form onSubmit={search} className="flex w-full items-center gap-2 sm:w-64">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
                <Input
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setNotFound(false);
                  }}
                  list="protein-names"
                  placeholder="Protein name or ID"
                  className={cn("pl-8", notFound && "border-amber/60")}
                  aria-label="Search protein"
                />
                <datalist id="protein-names">{shown?.nodes.map((n) => <option key={n.id} value={n.name} />)}</datalist>
              </div>
              <Button type="submit" size="sm">
                Find
              </Button>
            </form>
            <div className="w-full sm:w-48">
              <div className="mb-1.5 flex justify-between text-xs">
                <span className="text-muted">Min identity</span>
                <span className="font-mono text-teal">{Math.round(identity * 100)}%</span>
              </div>
              <Slider min={0.3} max={0.95} step={0.05} value={[identity]} onValueChange={([v]) => setIdentity(v)} onValueCommit={([v]) => setApplied((a) => ({ ...a, identity: +v.toFixed(2) }))} aria-label="Minimum identity" />
            </div>
            <div className="w-full sm:w-48">
              <div className="mb-1.5 flex justify-between text-xs">
                <span className="text-muted">Min coverage (both)</span>
                <span className="font-mono text-teal">{Math.round(coverage * 100)}%</span>
              </div>
              <Slider min={0.5} max={0.9} step={0.1} value={[coverage]} onValueChange={([v]) => setCoverage(v)} onValueCommit={([v]) => setApplied((a) => ({ ...a, coverage: +v.toFixed(1) }))} aria-label="Minimum coverage" />
            </div>
            <div className="ml-auto flex items-center gap-1">
              <Tip content="Zoom in">
                <Button size="icon" variant="ghost" onClick={() => graph.current?.zoom(1.4)} aria-label="Zoom in">
                  <ZoomIn />
                </Button>
              </Tip>
              <Tip content="Zoom out">
                <Button size="icon" variant="ghost" onClick={() => graph.current?.zoom(1 / 1.4)} aria-label="Zoom out">
                  <ZoomOut />
                </Button>
              </Tip>
              <Tip content="Fit to view">
                <Button size="icon" variant="ghost" onClick={() => graph.current?.fit()} aria-label="Fit to view">
                  <Maximize2 />
                </Button>
              </Tip>
              <Tip content="Reset thresholds, filters and selection">
                <Button size="icon" variant="ghost" onClick={reset} aria-label="Reset network">
                  <RotateCcw />
                </Button>
              </Tip>
            </div>
          </div>
          {notFound && <div className="px-4 pt-2 text-xs text-amber">No protein matches “{query}”.</div>}

          {/* cluster filter */}
          <div className="flex flex-wrap items-center gap-1.5 px-4 pt-3">
            <span className="mr-1 text-xs text-muted">Subgroups</span>
            {groups.map((g) => {
              const off = hidden.has(g);
              return (
                <button
                  key={g}
                  onClick={() => setHidden((h) => (h.has(g) ? new Set([...h].filter((x) => x !== g)) : new Set([...h, g])))}
                  aria-pressed={!off}
                  className={cn("flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[11px] transition", off ? "border-line text-muted/60" : "text-ink")}
                  style={off ? undefined : { borderColor: `${clusterColor(g)}66`, background: `${clusterColor(g)}14` }}
                >
                  <span className="size-2 rounded-full" style={{ background: off ? "#294157" : clusterColor(g) }} />
                  {g} <span className="text-muted">{counts[g]}</span>
                </button>
              );
            })}
          </div>

          {/* canvas */}
          <div className="relative m-4 h-[560px] overflow-hidden rounded-xl border border-line/70 bg-[radial-gradient(ellipse_at_center,#0f2236_0%,#091321_70%)] lg:h-[640px]">
            {net.error && !shown ? (
              <ErrorState message={net.error.message} onRetry={net.retry} />
            ) : shown ? (
              <NetworkGraph ref={graph} data={shown} selectedId={selected} hiddenClusters={hidden} onSelect={select} />
            ) : (
              <Skeleton className="h-full w-full" />
            )}
            {net.loading && shown && (
              <div className="absolute right-3 top-3 rounded-full border border-teal/40 bg-void/80 px-3 py-1 font-mono text-[11px] text-teal">Updating edges…</div>
            )}
            {shown && (
              <div className="pointer-events-none absolute bottom-3 left-3 right-3 flex flex-wrap justify-between gap-2 font-mono text-[10px] text-muted">
                <span>Node size ∝ number of connections (degree) · colour = subgroup</span>
                <span>scroll to zoom · drag to pan · click to select</span>
              </div>
            )}
          </div>

          {shown && (
            <div className="grid grid-cols-2 gap-4 border-t border-line/60 p-4 sm:grid-cols-4">
              <Metric label="Edges" value={num(shown.stats.edges)} hint={`≥ ${Math.round(shown.threshold.min_identity * 100)}% id, ≥ ${Math.round(shown.threshold.min_coverage * 100)}% cov`} />
              <Metric label="Components" value={shown.stats.components} accent="#4CA8D8" />
              <Metric label="Largest component" value={shown.stats.largest_component} accent="#69E8C3" hint="proteins" />
              <Metric label="Isolated proteins" value={shown.stats.isolated} accent="#E8B56B" hint="no edge at this threshold" />
            </div>
          )}
        </Panel>

        <div className="flex flex-col gap-6">
          <Panel className="min-h-80">
            <NodePanel node={node} onClose={() => select(null)} onSelect={select} />
          </Panel>
          <Panel>
            <PanelHeader
              eyebrow="Cytoscape export"
              title="Download network tables"
              description="CSV node and edge tables for File → Import → Network from File in Cytoscape Desktop."
              action={<InfoTip content="The default edge rule is ≥ 40% identity over ≥ 70% of both sequences, above the 25–35% twilight zone (Rost 1999)." />}
            />
            <div className="flex flex-col gap-2 p-5">
              <Button asChild size="sm" variant="secondary">
                <a href="/api/downloads/ssn_nodes" download>
                  <Download /> Nodes (ssn_nodes.csv)
                </a>
              </Button>
              <Button asChild size="sm" variant="secondary">
                <a href="/api/downloads/ssn_edges" download>
                  <Download /> Edges, default threshold (ssn_edges.csv)
                </a>
              </Button>
              <Button size="sm" variant="outline" onClick={exportCurrent} disabled={!shown}>
                <Download /> Edges at current threshold
              </Button>
            </div>
          </Panel>
          {shown && <p className="px-1 text-xs leading-relaxed text-muted">{shown.layout_note}</p>}
        </div>
      </div>

      {clustering.error ? (
        <Panel>
          <ErrorState message={clustering.error.message} onRetry={clustering.retry} />
        </Panel>
      ) : clustering.data ? (
        <ClusterCharts data={clustering.data} />
      ) : (
        <Skeleton className="h-[520px] rounded-[14px]" />
      )}
    </div>
  );
}
