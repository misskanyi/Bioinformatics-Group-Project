"""Read-only access to the cached analysis outputs (outputs/explorer/*).

Nothing here recomputes a scientific result: every number served by the API
comes from a table written by `python -m pet_explorer.pipeline` or
`analyze_pet_dataset.py`. Tables are loaded once and cached in memory.
"""

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from pet_explorer import config as C

UNKNOWN_EVIDENCE = "none"

# Files that may be downloaded through /api/downloads/{key}
DOWNLOADS = {
    "ssn_nodes": (C.NETWORK / "ssn_nodes.csv", "Cytoscape node table (sequence-similarity network)"),
    "ssn_edges": (C.NETWORK / "ssn_edges.csv", "Cytoscape edge table (identity >= 40%, coverage >= 70%)"),
    "proteins_csv": (C.F_PROTEINS, "298 usable PET-active proteins with evidence summary"),
    "proteins_fasta": (C.F_FASTA, "298 PET-active protein sequences (FASTA)"),
    "cluster_assignments": (C.CLUSTERING / "cluster_assignments.csv", "Cluster, subcluster, PCA and MDS coordinates"),
    "cluster_summary": (C.CLUSTERING / "cluster_summary.csv", "Per-cluster summary statistics"),
    "temperature_assays": (C.TEMPERATURE / "pet_temperature_assays.csv", "One row per PET assay with conditions"),
    "temperature_summary": (C.TEMPERATURE / "protein_temperature_summary.csv", "Per-protein temperature summary"),
    "comparable_series": (C.TEMPERATURE / "comparable_temperature_series.csv", "Comparable temperature series (>= 3 temperatures)"),
    "protein_organisms": (C.ORGANISMS / "protein_organisms.csv", "Per-protein organism with evidence level"),
    "organism_links": (C.ORGANISMS / "organism_links.csv", "Every protein-organism source record"),
    "quality_summary": (C.FEASIBILITY / "pet_dataset_quality_summary.csv", "Dataset quality metrics"),
}


def _read(path: Path, **kw) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{path.relative_to(C.ROOT)} is missing - run `python -m pet_explorer.pipeline`.")
    return pd.read_csv(path, **kw)


def records(df: pd.DataFrame) -> list:
    """DataFrame -> JSON-safe list of dicts (NaN -> None)."""
    return df.astype(object).where(df.notna(), None).to_dict("records")


def split(value) -> list:
    if value is None or (isinstance(value, float) and np.isnan(value)) or value == "":
        return []
    return [v.strip() for v in str(value).split(";") if v.strip()]


def floats(value) -> list:
    return [float(v) for v in split(value)]


@lru_cache
def proteins() -> pd.DataFrame:
    p = _read(C.F_PROTEINS)
    a = _read(C.CLUSTERING / "cluster_assignments.csv")[["protein_id", "cluster", "subcluster"]]
    return p.merge(a, on="protein_id", how="left")


@lru_cache
def assignments() -> pd.DataFrame:
    return _read(C.CLUSTERING / "cluster_assignments.csv")


@lru_cache
def features() -> pd.DataFrame:
    return _read(C.CLUSTERING / "sequence_features.csv")


@lru_cache
def cluster_summary() -> pd.DataFrame:
    return _read(C.CLUSTERING / "cluster_summary.csv")


@lru_cache
def pairs() -> pd.DataFrame:
    return _read(C.F_PAIRS)


@lru_cache
def layout() -> pd.DataFrame:
    return _read(C.NETWORK / "ssn_layout.csv")


@lru_cache
def sensitivity() -> pd.DataFrame:
    return _read(C.NETWORK / "edge_threshold_sensitivity.csv")


@lru_cache
def temperature_assays() -> pd.DataFrame:
    a = _read(C.TEMPERATURE / "pet_temperature_assays.csv")
    return a[a.in_pet_active_set].reset_index(drop=True)


@lru_cache
def temperature_summary() -> pd.DataFrame:
    return _read(C.TEMPERATURE / "protein_temperature_summary.csv")


@lru_cache
def comparable_series() -> pd.DataFrame:
    return _read(C.TEMPERATURE / "comparable_temperature_series.csv")


@lru_cache
def organisms() -> pd.DataFrame:
    return _read(C.ORGANISMS / "protein_organisms.csv")


@lru_cache
def organism_links() -> pd.DataFrame:
    path = C.ORGANISMS / "organism_links.csv"
    return pd.read_csv(path, dtype={"taxonomy_id": str}).fillna("") if path.exists() else pd.DataFrame()


@lru_cache
def quality_summary() -> pd.DataFrame:
    return _read(C.FEASIBILITY / "pet_dataset_quality_summary.csv").dropna(subset=["metric"])


@lru_cache
def inventory() -> pd.DataFrame:
    return _read(C.FEASIBILITY / "tables" / "dataset_inventory.csv")


@lru_cache
def qc_checks() -> pd.DataFrame:
    return _read(C.CLEAN / "qc_checks.csv")


@lru_cache
def leave_one_out() -> pd.DataFrame:
    return _read(C.MATCHING / "leave_one_out_nearest_neighbour.csv")


@lru_cache
def degree_at_default() -> dict:
    n = _read(C.NETWORK / "ssn_nodes.csv")
    return dict(zip(n.id, n.degree))


def has_organism(org_row) -> bool:
    return org_row.get("organism_evidence", UNKNOWN_EVIDENCE) != UNKNOWN_EVIDENCE


def organism_row(pid: int) -> dict:
    o = organisms()
    r = o[o.protein_id == pid]
    return records(r)[0] if len(r) else {}


def protein_card(pid: int) -> dict:
    """Evidence summary for one reference protein (used by matching and detail views)."""
    p = proteins()
    row = records(p[p.protein_id == pid])[0]
    t = temperature_summary()
    trow = records(t[t.protein_id == pid])
    trow = trow[0] if trow else {}
    org = organism_row(pid)
    return {
        "protein_id": pid,
        "protein_name": row["protein_name"],
        "cluster": row["cluster"],
        "subcluster": row["subcluster"],
        "sequence_length": row["sequence_length"],
        "pet_label": row["pet_label"],
        "label_confidence": row["label_confidence"],
        "n_pet_assays": row["n_pet_assays"],
        "n_positive_assays": row["n_positive_assays"],
        "n_negative_assays": row["n_negative_assays"],
        "n_publications": row["n_publications"],
        "dois": split(row["dois"]),
        "substrate_forms": split(row["substrate_forms"]),
        "enzyme_preparations": split(row["enzyme_preparations"]),
        "ph_range": row["ph_range"],
        "temperatures_tested_c": floats(trow.get("temperatures_tested_c")),
        "temperatures_with_activity_c": floats(trow.get("temperatures_with_activity_c")),
        "temperatures_without_detected_activity_c": floats(trow.get("temperatures_without_detected_activity_c")),
        "temperature_optimum_status": trow.get("temperature_optimum_status"),
        "optimum_status_category": trow.get("optimum_status_category"),
        "organism": org.get("organism"),
        "organism_evidence": org.get("organism_evidence", UNKNOWN_EVIDENCE),
        "organism_association": org.get("association_type"),
        "organism_confidence": org.get("confidence"),
        "organism_sources_disagree": bool(org.get("sources_disagree") or False),
        "taxonomy_id": org.get("taxonomy_id"),
        "isolation_environment": org.get("isolation_environment"),
        "isolation_sample_type": org.get("isolation_sample_type"),
        "isolation_location": org.get("isolation_location"),
        "degree": int(degree_at_default().get(pid, 0)),
    }
