// Response types for the FastAPI backend (backend/api/*). Keep in sync.

export type OrganismEvidence = "exact_sequence" | "contained_sequence" | "pazy_curation_text" | "none";
export type AssayOutcome = "detected" | "not detected" | "unclear" | "excluded";

export interface Health {
  status: "ok";
  proteins: number;
  organism_table: boolean;
  matcher_ready: boolean;
}

export interface OverviewStats {
  proteins: number;
  publications: number;
  clusters: number;
  subclusters: number;
  proteins_with_organism: number;
  organism_names: number;
  proteins_with_temperature: number;
  pet_assays: number;
  assays_detected: number;
  network_edges: number;
  network_components: number;
  network_isolated: number;
}

export interface Overview {
  stats: OverviewStats;
  insights: { label: string; value: string; detail: string }[];
  cluster_sizes: { subcluster: string; n: number }[];
}

export interface ProteinIndexRow {
  protein_id: number;
  protein_name: string;
  cluster: string;
  subcluster: string;
  sequence_length: number;
  organism: string | null;
  organism_evidence: OrganismEvidence | null;
}

export interface ProteinCard {
  protein_id: number;
  protein_name: string;
  cluster: string;
  subcluster: string;
  sequence_length: number;
  pet_label: string;
  label_confidence: string;
  n_pet_assays: number;
  n_positive_assays: number;
  n_negative_assays: number;
  n_publications: number;
  dois: string[];
  substrate_forms: string[];
  enzyme_preparations: string[];
  ph_range: string | null;
  temperatures_tested_c: number[];
  temperatures_with_activity_c: number[];
  temperatures_without_detected_activity_c: number[];
  temperature_optimum_status: string | null;
  optimum_status_category: string | null;
  organism: string | null;
  organism_evidence: OrganismEvidence;
  organism_association: string | null;
  organism_confidence: string | null;
  organism_sources_disagree: boolean;
  taxonomy_id: string | null;
  isolation_environment: string | null;
  isolation_sample_type: string | null;
  isolation_location: string | null;
  degree: number;
}

export interface OrganismLink {
  organism: string;
  taxonomy_id: string;
  evidence_level: OrganismEvidence;
  source: string;
  source_record: string;
  accession: string;
  detail: string;
}

export interface ProteinDetail extends ProteinCard {
  sequence: string;
  closest_relative_with_known_organism: string | null;
  closest_relative_note: string | null;
  organism_links: OrganismLink[];
  nearest_references: { protein_id: number; protein_name: string; identity: number; min_coverage: number }[];
}

export interface Example {
  protein_id: number;
  protein_name: string;
  subcluster: string;
  length: number;
  fasta: string;
}

export interface MatchMethod {
  algorithm: string;
  matrix: string;
  gap_open: number;
  gap_extend: number;
  ranking: string;
  identity_definition: string;
  coverage_definition: string;
  shuffle_control: string;
  reference_set_size: number;
  bands: { min_identity: number; min_coverage: number; label: string }[];
  no_match_label: string;
  min_length: number;
  max_length: number;
}

export interface Hit {
  rank: number;
  protein_id: number;
  protein_name: string;
  identity: number;
  query_coverage: number;
  target_coverage: number;
  aligned_columns: number;
  raw_score: number;
  normalised_score: number;
  shuffled_z: number;
  query_range: [number, number];
  target_range: [number, number];
  interpretation: string;
  aligned_query: string;
  aligned_target: string;
  reference: ProteinCard;
}

export interface MatchResult {
  header: string;
  sequence: string;
  length: number;
  hits: Hit[];
  method: MatchMethod;
}

export interface NetworkNode {
  id: number;
  name: string;
  cluster: string;
  subcluster: string;
  length: number;
  degree: number;
  component: number;
  x: number;
  y: number;
  organism: string | null;
  organism_evidence: OrganismEvidence | null;
  n_temperatures: number;
}

export interface NetworkData {
  threshold: { min_identity: number; min_coverage: number };
  nodes: NetworkNode[];
  edges: [number, number, number, number][];
  stats: { edges: number; components: number; largest_component: number; isolated: number };
  layout_note: string;
}

export interface ClusterSummaryRow {
  subcluster: string;
  cluster: string;
  n_proteins: number;
  median_length: number;
  length_range: string;
  mean_within_identity_pct: number | null;
  coherence: string;
  with_gxsxg: string;
  top_gxsxg_variants: string;
  median_pI: number;
  n_publications: number;
  top_publication_share: string;
  example_members: string;
}

export interface Clustering {
  subclusters: string[];
  points: { id: number; name: string; subcluster: string; pca: [number, number]; mds: [number, number] }[];
  pca_variance: number[];
  mds_variance: number[];
  composition: ({ aa: string; all: number } & Record<string, number | string>)[];
  summary: ClusterSummaryRow[];
  selection: {
    final_method: string;
    final_parameter: number;
    selected_row: { silhouette_alignment: number; stability_ari_mean: number; n_clusters: number };
    [k: string]: unknown;
  };
  heatmap: { ids: number[]; subclusters: string[]; names: string[]; matrix: number[][] };
}

export type AssayTuple = [
  number, // protein_id
  string, // protein_name
  string, // subcluster
  number | null, // temperature_c
  number | null, // ph
  number | null, // duration_value
  string | null, // duration_unit
  string | null, // material_name
  string | null, // material_form
  number | null, // crystallinity_percent
  string | null, // enzyme_preparation
  string | null, // detection_methods
  string | null, // metric_types
  AssayOutcome, // degradation_detected
  string | null, // outcome_reason
  string, // literature_doi
];

export interface Assay {
  protein_id: number;
  protein_name: string;
  subcluster: string;
  temperature_c: number | null;
  ph: number | null;
  duration_value: number | null;
  duration_unit: string | null;
  material_name: string | null;
  material_form: string | null;
  crystallinity_percent: number | null;
  enzyme_preparation: string | null;
  detection_methods: string | null;
  metric_types: string | null;
  degradation_detected: AssayOutcome;
  outcome_reason: string | null;
  literature_doi: string;
}

export interface ProteinTemperature {
  protein_id: number;
  protein_name: string;
  subcluster: string;
  optimum_status_category: string;
  n_pet_assays: number;
  n_temperatures_tested: number;
  temperatures_tested_c: string | null;
  temperatures_with_activity_c: string | null;
  temperatures_without_detected_activity_c: string | null;
  temperature_optimum_status: string;
  ph_values_tested: string | null;
  n_comparable_series: number;
}

export interface TemperatureSeries {
  protein_id: number;
  doi: string;
  metric: string;
  unit: string;
  ph: number | null;
  temperatures: number[];
  values: number[];
  best_tested_temperature_c: number;
  best_at_edge: string;
  context: string;
}

export interface Conditions {
  assays: AssayTuple[];
  assay_fields: string[];
  proteins: ProteinTemperature[];
  series: TemperatureSeries[];
  notes: string[];
}

export interface OrganismCard {
  organism: string;
  genus: string;
  uncultured: boolean;
  taxonomy_ids: string[];
  sources: string[];
  accessions: string[];
  isolation_environment: string[];
  isolation_sample_type: string[];
  isolation_location: string[];
  best_evidence: OrganismEvidence;
  n_proteins: number;
  proteins: {
    protein_id: number;
    protein_name: string;
    subcluster: string;
    evidence: OrganismEvidence;
    confidence: string;
    sources_disagree: boolean;
  }[];
}

export interface Organisms {
  organisms: OrganismCard[];
  evidence_labels: Record<OrganismEvidence, string>;
  evidence_counts: Record<OrganismEvidence, number>;
  n_proteins: number;
  unknown: { protein_id: number; protein_name: string; subcluster: string; closest_relative: string | null }[];
  context_note: string;
}

export interface Datasets {
  inventory: {
    file: string;
    format: string;
    records: number;
    fields: string;
    missing_values: number | null;
    unique_ids: number | null;
    duplicate_sequences: number | null;
    notes: string;
  }[];
  quality: { metric: string; value: string | number; how_calculated: string }[];
  qc_checks: { check: string; value: number; passed: boolean }[];
  pipeline: { stage: string; detail: string; count: string }[];
  coverage: Record<string, number>;
  leave_one_out: { description: string; bands: Record<string, number>; median_identity: number };
  references: { doi: string; n_proteins: number }[];
  limitations: string[];
  downloads: { key: string; file: string; description: string; available: boolean }[];
}
