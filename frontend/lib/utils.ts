import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const pct = (v: number, digits = 1) => `${(100 * v).toFixed(digits)}%`;

export const num = (v: number) => v.toLocaleString("en-GB");

export const doiUrl = (doi: string) => `https://doi.org/${doi}`;

export function groupKey(label: string): [number, string] {
  const m = /^G(\d+)([a-z]?)$/.exec(label);
  return m ? [Number(m[1]), m[2]] : [1e6, label];
}

export function sortGroups(labels: string[]) {
  return [...labels].sort((a, b) => {
    const [na, sa] = groupKey(a);
    const [nb, sb] = groupKey(b);
    return na - nb || sa.localeCompare(sb);
  });
}

export function parseNums(v: string | null | undefined): number[] {
  if (!v) return [];
  return v
    .split(";")
    .map((x) => Number(x.trim()))
    .filter((x) => Number.isFinite(x));
}

export const fmtTemps = (t: number[]) => (t.length ? t.map((x) => `${x}`).join(", ") + " °C" : "—");
