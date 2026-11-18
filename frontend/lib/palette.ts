import type { AssayOutcome, OrganismEvidence } from "@/types/api";

// Every colour is a CSS variable defined for both themes in app/globals.css,
// so it works in inline styles and SVG attributes and switches with the theme.
// Canvas / Cytoscape code resolves them with useResolvedColors (lib/theme.ts).
const v = (name: string) => `var(--color-${name})`;

export const C = {
  aqua: v("aqua"),
  sky: v("sky"),
  mint: v("mint"),
  amber: v("amber"),
  violet: v("violet"),
  rose: v("rose"),
  slate: v("slate"),
  muted: v("muted"),
  ink: v("ink"),
  teal: v("teal"),
  cyan: v("cyan"),
  electric: v("electric"),
  line: v("line"),
  void: v("void"),
} as const;

/** Translucent version of any colour (works with var()). `pct` = opacity in percent. */
export const tint = (color: string, pct: number) => `color-mix(in srgb, ${color} ${pct}%, transparent)`;

// One fixed colour per sequence subgroup, used by every chart and the network.
export const CLUSTER_COLORS: Record<string, string> = {
  G1a: v("aqua"),
  G1b: v("sky"),
  G2: v("amber"),
  G3: v("violet"),
  G4: v("rose"),
  G5: v("lime"),
  G6: v("orange"),
  G7: v("pearl"),
};

export const clusterColor = (c: string) => CLUSTER_COLORS[c] ?? C.muted;

// Evidence colours are consistent across the app:
//   experimental = mint, computational similarity = cyan,
//   documented organism = violet, missing / uncertain = amber.
export const EVIDENCE = {
  experimental: { color: C.mint, label: "Experimentally verified" },
  computational: { color: C.sky, label: "Computational similarity" },
  organism: { color: C.violet, label: "Documented organism" },
  uncertain: { color: C.amber, label: "Missing / uncertain" },
} as const;

export const OUTCOME_COLORS: Record<AssayOutcome, string> = {
  detected: C.mint,
  "not detected": C.rose,
  unclear: C.amber,
  excluded: C.slate,
};

export const OUTCOME_LABELS: Record<AssayOutcome, string> = {
  detected: "PET breakdown detected",
  "not detected": "No breakdown detected (reported method)",
  unclear: "Unclear",
  excluded: "Excluded",
};

export const ORGANISM_EVIDENCE: Record<OrganismEvidence, { label: string; short: string; color: string }> = {
  exact_sequence: { label: "Directly documented — identical database sequence", short: "Identical sequence", color: C.violet },
  contained_sequence: {
    label: "Database match — precursor / mature form of the same sequence",
    short: "Precursor / mature form",
    color: v("periwinkle"),
  },
  pazy_curation_text: { label: "Reported in literature text — not sequence-verified", short: "Literature text", color: C.sky },
  none: { label: "Unknown — insufficient evidence", short: "Unknown", color: C.amber },
};

export const CHART = {
  grid: "var(--chart-grid)",
  axis: C.muted,
  text: C.ink,
  cursor: "var(--chart-cursor)",
  dotBg: "var(--chart-dot-bg)",
};
