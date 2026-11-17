"use client";

import type { Core, ElementDefinition, StylesheetJson } from "cytoscape";
import { useReducedMotion } from "motion/react";
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";

import { C, CLUSTER_COLORS } from "@/lib/palette";
import { useResolvedColors, useTheme } from "@/lib/theme";
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
const COLOR_VARS: Record<string, string> & { fallback: string; ink: string; bg: string; edge: string; hl: string } = {
  ...CLUSTER_COLORS,
  fallback: C.muted,
  ink: C.ink,
  bg: C.void,
  edge: C.sky,
  hl: C.aqua,
};
type Colors = typeof COLOR_VARS;

function elements(data: NetworkData, colors: Colors): ElementDefinition[] {
  const nodes: ElementDefinition[] = data.nodes.map((n) => ({
    group: "nodes",
    data: { id: String(n.id), label: n.name, color: colors[n.subcluster] ?? colors.fallback, degree: n.degree, subcluster: n.subcluster },
    position: { x: n.x * SCALE, y: n.y * SCALE },
  }));
  const edges: ElementDefinition[] = data.edges.map(([s, t, identity]) => ({
    group: "edges",
    data: { id: `${s}-${t}`, source: String(s), target: String(t), identity },
  }));
  return [...nodes, ...edges];
}

/** Stylesheet for the current theme. Edge opacity stays a function of identity in both themes. */
function stylesheet(colors: Colors, light: boolean, preview: boolean, maxDeg: number): StylesheetJson {
  const size = `mapData(degree, 0, ${maxDeg}, ${preview ? 4 : 7}, ${preview ? 11 : 22})`;
  return [
    {
      selector: "node",
      style: {
        "background-color": "data(color)",
        width: size,
        height: size,
        "border-width": light ? 0.6 : 0,
        "border-color": colors.bg,
        "underlay-color": "data(color)",
        "underlay-opacity": light ? 0.1 : 0.12,
        "underlay-padding": 3,
        "underlay-shape": "ellipse",
        label: "",
        color: colors.ink,
        "font-size": 9,
        "font-family": "var(--font-geist-mono), monospace",
        "text-valign": "top",
        "text-margin-y": -4,
        "text-outline-color": colors.bg,
        "text-outline-width": 2,
        "transition-property": "opacity",
        "transition-duration": 220,
      },
    },
    {
      selector: "edge",
      style: {
        width: light ? 0.7 : 0.6,
        "line-color": colors.edge,
        opacity: `mapData(identity, 0.3, 1, ${light ? 0.08 : 0.05}, ${preview ? 0.35 : light ? 0.36 : 0.28})`,
        "curve-style": "haystack",
        // no edge transitions: with ~14k edges they would cost more than they show
      },
    },
    // entrance: elements start hidden and transition in when the class is removed
    { selector: ".entering", style: { opacity: 0 } },
    { selector: ".faded, .dim", style: { opacity: 0.08 } },
    { selector: "edge.faded, edge.dim", style: { opacity: 0.015 } },
    { selector: "node.neighbour", style: { label: "data(label)", "underlay-opacity": 0.3, opacity: 1 } },
    { selector: "node.neighbour-quiet", style: { "underlay-opacity": 0.3, opacity: 1 } },
    { selector: "edge.hl, edge.hover-hl", style: { "line-color": colors.hl, opacity: 0.75, width: 1.2 } },
    {
      selector: "node.hover",
      style: { label: "data(label)", "underlay-opacity": 0.45, "underlay-padding": 6, "z-index": 98 },
    },
    {
      selector: "node.focus",
      style: {
        label: "data(label)",
        "font-size": 12,
        "border-width": 2,
        "border-color": colors.ink,
        "underlay-opacity": 0.55,
        "underlay-padding": 8,
        "z-index": 99,
      },
    },
  ] as StylesheetJson;
}

/**
 * Protein sequence-similarity network (Cytoscape, preset layout).
 * Positions come from the backend layout, so nothing keeps moving after load:
 * the only motion is a one-off entrance and the user's own zoom / pan.
 */
export const NetworkGraph = forwardRef<NetworkGraphHandle, Props>(function NetworkGraph(
  { data, selectedId, hiddenClusters, onSelect, preview, className },
  ref,
) {
  const container = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const selectedRef = useRef(selectedId);
  selectedRef.current = selectedId;

  const colors = useResolvedColors(COLOR_VARS);
  const light = useTheme() === "light";
  const reduce = useReducedMotion();
  const themeRef = useRef({ colors, light });
  themeRef.current = { colors, light };
  const maxDeg = Math.max(1, ...data.nodes.map((n) => n.degree));

  useImperativeHandle(ref, () => ({
    fit: () => cyRef.current?.animate({ fit: { eles: cyRef.current.elements(":visible"), padding: 30 } }, { duration: 400, easing: "ease-in-out-cubic" }),
    zoom: (f) => {
      const cy = cyRef.current;
      if (!cy) return;
      cy.animate({ zoom: { level: cy.zoom() * f, position: { x: cy.width() / 2, y: cy.height() / 2 } } } as never, { duration: 220, easing: "ease-out-cubic" });
    },
    focus: (id) => {
      const cy = cyRef.current;
      const n = cy?.getElementById(String(id));
      if (!cy || !n || n.empty()) return;
      const hood = n.closedNeighborhood("node:visible");
      if (hood.length > 1) cy.animate({ fit: { eles: hood, padding: 60 } }, { duration: 450, easing: "ease-in-out-cubic" });
      else cy.animate({ center: { eles: n }, zoom: Math.min(2.5, Math.max(cy.zoom(), 1.4)) }, { duration: 450, easing: "ease-in-out-cubic" });
    },
  }));

  // (re)build the graph when the data (threshold) changes
  useEffect(() => {
    let cy: Core | undefined;
    let cancelled = false;
    const timers: number[] = [];
    import("cytoscape").then(({ default: cytoscape }) => {
      if (cancelled || !container.current) return;
      const { colors: c, light: l } = themeRef.current;
      cy = cytoscape({
        container: container.current,
        elements: elements(data, c),
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
        style: stylesheet(c, l, !!preview, maxDeg),
      });
      cy.on("tap", "node", (e) => onSelectRef.current?.(Number(e.target.id())));
      cy.on("tap", (e) => {
        if (e.target === cy) onSelectRef.current?.(null);
      });
      if (!preview) {
        // Hover: show the protein's label and, when nothing is selected, light up its direct relatives.
        cy.on("mouseover", "node", (e) => {
          const n = e.target;
          n.addClass("hover");
          if (selectedRef.current == null && cy) {
            const hood = n.closedNeighborhood();
            cy.batch(() => {
              cy!.elements().not(hood).addClass("dim");
              n.connectedEdges().addClass("hover-hl");
            });
          }
          if (container.current) container.current.style.cursor = "pointer";
        });
        cy.on("mouseout", "node", (e) => {
          e.target.removeClass("hover");
          cy?.batch(() => cy!.elements().removeClass("dim hover-hl"));
          if (container.current) container.current.style.cursor = "";
        });
      }
      cyRef.current = cy;
      applyState();

      // One-off entrance: nodes fade in from the centre outwards, then the edges; the view eases into place.
      const motion = !reduce && !preview;
      if (motion) {
        const box = cy.extent();
        const cx = (box.x1 + box.x2) / 2;
        const cyy = (box.y1 + box.y2) / 2;
        const reach = Math.max(1, Math.hypot(box.w, box.h) / 2);
        cy.elements().addClass("entering");
        const target = { zoom: cy.zoom(), pan: { ...cy.pan() } };
        cy.zoom(target.zoom * 0.88);
        cy.center();
        cy.animate({ zoom: target.zoom, pan: target.pan }, { duration: 750, easing: "ease-out-cubic" });
        cy.nodes().forEach((n) => {
          const p = n.position();
          const delay = Math.round((Math.hypot(p.x - cx, p.y - cyy) / reach) * 420);
          timers.push(window.setTimeout(() => n.removeClass("entering"), delay));
        });
        timers.push(window.setTimeout(() => cy?.edges().removeClass("entering"), 380));
      }
    });
    return () => {
      cancelled = true;
      timers.forEach(clearTimeout);
      cy?.destroy();
      cyRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, preview]);

  // theme change: recolour in place (no rebuild, keeps zoom, pan and selection)
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.batch(() => {
      cy.nodes().forEach((n) => {
        n.data("color", colors[n.data("subcluster") as string] ?? colors.fallback);
      });
    });
    cy.style(stylesheet(colors, light, !!preview, maxDeg));
  }, [colors, light, preview, maxDeg]);

  function applyState() {
    const cy = cyRef.current;
    if (!cy) return;
    cy.batch(() => {
      cy.elements().removeClass("faded hl neighbour neighbour-quiet focus dim hover-hl");
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
      className={cn("reveal h-full w-full", className)}
      role="img"
      aria-label={`Protein sequence-similarity network: ${data.nodes.length} proteins and ${data.edges.length} similarity edges`}
    />
  );
});
