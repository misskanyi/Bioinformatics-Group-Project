// Standard physicochemical residue classes (side-chain properties).
export const RESIDUE_CLASS: Record<string, { name: string; color: string }> = {
  hydrophobic: { name: "Hydrophobic (A V L I M)", color: "#69E8C3" },
  aromatic: { name: "Aromatic (F W Y)", color: "#48E1CD" },
  polar: { name: "Polar (S T N Q C)", color: "#4CA8D8" },
  acidic: { name: "Acidic (D E)", color: "#EF8A9A" },
  basic: { name: "Basic (K R H)", color: "#B49CF5" },
  special: { name: "Special (G P)", color: "#E8B56B" },
};

const MAP: Record<string, keyof typeof RESIDUE_CLASS> = {
  A: "hydrophobic", V: "hydrophobic", L: "hydrophobic", I: "hydrophobic", M: "hydrophobic",
  F: "aromatic", W: "aromatic", Y: "aromatic",
  S: "polar", T: "polar", N: "polar", Q: "polar", C: "polar",
  D: "acidic", E: "acidic",
  K: "basic", R: "basic", H: "basic",
  G: "special", P: "special",
};

export const residueColor = (aa: string) => (MAP[aa] ? RESIDUE_CLASS[MAP[aa]].color : undefined);

export const STANDARD_AA = new Set("ACDEFGHIKLMNPQRSTVWY");

export interface LocalCheck {
  header: string | null;
  sequence: string;
  invalid: string[];
  multiple: boolean;
  looksNucleotide: boolean;
}

/** Light client-side pre-check for instant feedback; the backend validation is authoritative. */
export function localCheck(text: string): LocalCheck {
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  const headers = lines.filter((l) => l.startsWith(">"));
  const header = lines[0]?.startsWith(">") ? lines[0].slice(1).trim() : null;
  const seq = lines
    .filter((l) => !l.startsWith(">"))
    .join("")
    .replace(/[\s\d]/g, "")
    .toUpperCase()
    .replace(/\*$/, "");
  const invalid = [...new Set(seq.split("").filter((c) => !STANDARD_AA.has(c)))];
  return {
    header,
    sequence: seq,
    invalid,
    multiple: headers.length > 1,
    looksNucleotide: seq.length >= 30 && /^[ACGTUN]+$/.test(seq),
  };
}
