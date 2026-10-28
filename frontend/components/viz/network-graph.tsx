"use client";

import type { Core, ElementDefinition } from "cytoscape";
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";

import { clusterColor } from "@/lib/palette";
import { cn } from "@/lib/utils";
import type { NetworkData } from "@/types/api";

export interface NetworkGraphHandle {
  fit: () => void;
  zoom: (factor: number) => void;
  focus: (id: number) => void;
}

interface Props {
  data: NetworkData;
  selectedId?: number | null;
  hiddenClusters?: Set<string>;
  onSelect?: (id: number | null) => void;
  preview?: boolean;
  className?: string;
}

const SCALE = 900;

function elements(data: NetworkData): ElementDefinition[] {
  const nodes: ElementDefinition[] = data.nodes.map((n) => ({
    group: "nodes",
    data: { id: String(n.id), label: n.name, color: clusterColor(n.subcluster), degree: n.degree, subcluster: n.subcluster },
    position: { x: n.x * SCALE, y: n.y * SCALE },
  }));
  const edges: ElementDefinition[] = data.edges.map(([s, t, identity]) => ({
    group: "edges",
    data: { id: `${s}-${t}`, source: String(s), target: String(t), identity },
  }));
  return [...nodes, ...edges];
}

export const NetworkGraph = forwardRef<NetworkGraphHandle, Props>(function NetworkGraph(
  { data, selectedId, hiddenClusters, onSelect, preview, className },
  ref,
) {
  const container = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  useImperativeHandle(ref, () => ({
    fit: () => cyRef.current?.animate({ fit: { eles: cyRef.current.elements(":visible"), padding: 30 } }, { duration: 400 }),
    zoom: (f) => {
      const cy = cyRef.current;
      if (!cy) return;
      cy.animate({ zoom: { level: cy.zoom() * f, position: { x: cy.width() / 2, y: cy.height() / 2 } } } as never, { duration: 200 });
    },
    focus: (id) => {
      const cy = cyRef.current;
      const n = cy?.getElementById(String(id));
      if (!cy || !n || n.empty()) return;
      const hood = n.closedNeighborhood("node:visible");
      if (hood.length > 1) cy.animate({ fit: { eles: hood, padding: 60 } }, { duration: 450 });
      else cy.animate({ center: { eles: n }, zoom: Math.min(2.5, Math.max(cy.zoom(), 1.4)) }, { duration: 450 });
    },
  }));

  // (re)build the graph when the data (threshold) changes
  useEffect(() => {
    let cy: Core | undefined;
    let cancelled = false;
    const maxDeg = Math.max(1, ...data.nodes.map((n) => n.degree));
    import("cytoscape").then(({ default: cytoscape }) => {
      if (cancelled || !container.current) return;
      cy = cytoscape({
        container: container.current,
        elements: elements(data),
        layout: { name: "preset", fit: true, padding: preview ? 12 : 30 },
        minZoom: 0.2,
        maxZoom: 6,
        wheelSensitivity: 0.3,
        userZoomingEnabled: !preview,
        userPanningEnabled: !preview,
        boxSelectionEnabled: false,
        autoungrabify: true,
        textureOnViewport: data.edges.length > 4000,
        hideEdgesOnViewport: data.edges.length > 8000,
        style: [
          {
            selector: "node",
            style: {
              "background-color": "data(color)",
              width: `mapData(degree, 0, ${maxDeg}, ${preview ? 4 : 7}, ${preview ? 11 : 22})`,
              height: `mapData(degree, 0, ${maxDeg}, ${preview ? 4 : 7}, ${preview ? 11 : 22})`,
              "border-width": 0,
              "underlay-color": "data(color)",
              "underlay-opacity": 0.12,
              "underlay-padding": 3,
              "underlay-shape": "ellipse",
              label: "",
              color: "#F0F8FF",
              "font-size": 9,
              "font-family": "var(--font-geist-mono), monospace",
              "text-valign": "top",
              "text-margin-y": -4,
              "text-outline-color": "#091321",
              "text-outline-width": 2,
              "transition-property": "opacity",
              "transition-duration": 200,
            } as never,
          },
          {
            selector: "edge",
            style: {
              width: 0.6,
              "line-color": "#4CA8D8",
              opacity: `mapData(identity, 0.3, 1, 0.05, ${preview ? 0.35 : 0.28})`,
              "curve-style": "haystack",
            } as never,
          },
          { selector: ".faded", style: { opacity: 0.08 } },
          { selector: "edge.faded", style: { opacity: 0.015 } },
          {
            selector: "node.neighbour",
            style: { label: "data(label)", "underlay-opacity": 0.3, opacity: 1 } as never,
          },
          { selector: "node.neighbour-quiet", style: { "underlay-opacity": 0.3, opacity: 1 } as never },
          { selector: "edge.hl", style: { "line-color": "#48E1CD", opacity: 0.75, width: 1.2 } as never },
          {
            selector: "node.focus",
            style: {
              label: "data(label)",
              "font-size": 12,
              "border-width": 2,
              "border-color": "#F0F8FF",
              "underlay-opacity": 0.55,
              "underlay-padding": 8,
              "z-index": 99,
            } as never,
          },
        ],
      });
      cy.on("tap", "node", (e) => onSelectRef.current?.(Number(e.target.id())));
      cy.on("tap", (e) => {
        if (e.target === cy) onSelectRef.current?.(null);
      });
      if (!preview) {
        cy.on("mouseover", "node", (e) => e.target.style("label", e.target.data("label")));
        cy.on("mouseout", "node", (e) => {
          if (!e.target.hasClass("focus") && !e.target.hasClass("neighbour")) e.target.removeStyle("label");
        });
      }
      cyRef.current = cy;
      applyState();
    });
    return () => {
      cancelled = true;
      cy?.destroy();
      cyRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, preview]);

  function applyState() {
    const cy = cyRef.current;
    if (!cy) return;
    cy.batch(() => {
      cy.elements().removeClass("faded hl neighbour neighbour-quiet focus");
      cy.nodes().removeStyle("label");
      cy.nodes().forEach((n) => {
        n.style("display", hiddenClusters?.has(n.data("subcluster")) ? "none" : "element");
      });
      if (selectedId != null) {
        const n = cy.getElementById(String(selectedId));
        if (n.nonempty()) {
          const hood = n.closedNeighborhood();
          cy.elements().not(hood).addClass("faded");
          n.connectedEdges().addClass("hl");
          const nb = n.neighborhood("node");
          // label neighbours only when there are few enough to stay readable
          nb.addClass(nb.length <= 25 ? "neighbour" : "neighbour-quiet");
          n.addClass("focus");
        }
      }
    });
  }

  useEffect(applyState, [selectedId, hiddenClusters]);  

  return (
    <div
      ref={container}
      className={cn("h-full w-full", className)}
      role="img"
      aria-label={`Protein sequence-similarity network: ${data.nodes.length} proteins and ${data.edges.length} similarity edges`}
    />
  );
});
