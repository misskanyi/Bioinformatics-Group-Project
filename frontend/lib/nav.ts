import { Database, FlaskConical, GraduationCap, Microscope, Target, type LucideIcon } from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  description: string;
  /** Sub-pages shown as a sidebar submenu, addressed as `${href}?section=id`. The first is the default. */
  sections?: readonly { id: string; label: string }[];
}

/** Sections inside Data Preparation & Exploration (?section=…). */
export const DATA_SECTIONS = [
  { id: "acquisition", label: "Data acquisition & QC" },
  { id: "exploration", label: "Exploratory analysis" },
  { id: "network", label: "Similarity network" },
  { id: "conditions", label: "Assay conditions" },
  { id: "organisms", label: "Organisms" },
] as const;

export type DataSection = (typeof DATA_SECTIONS)[number]["id"];

/** The five research pages. Each maps to one stage of the investigation. */
export const MAIN_NAV: NavItem[] = [
  { href: "/overview", label: "Research Overview", icon: Target, description: "Question, objectives and data sources" },
  { href: "/data", label: "Data Preparation & Exploration", icon: Database, description: "Acquisition, quality control, sequence analysis", sections: DATA_SECTIONS },
  { href: "/discovery", label: "Enzyme Prediction & Discovery", icon: FlaskConical, description: "Sequence matching and activity prediction" },
  { href: "/validation", label: "Model Validation", icon: Microscope, description: "Is the machine-learning approach reliable?" },
  { href: "/conclusions", label: "Conclusions & Recommendations", icon: GraduationCap, description: "Findings, limitations and next steps" },
];

export const FOOTER_NAV: NavItem[] = [];

export const networkHref = (proteinId: number) => `/data?section=network&protein=${proteinId}`;
export const sequenceHref = (proteinId: number) => `/discovery?protein=${proteinId}`;

export function navFor(pathname: string) {
  return MAIN_NAV.find((n) => pathname.startsWith(n.href.split("#")[0]));
}
