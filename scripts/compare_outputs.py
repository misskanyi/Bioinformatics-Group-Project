"""Compare freshly rebuilt analysis outputs with a reference copy, using tolerances.

    python scripts/compare_outputs.py REFERENCE_DIR REBUILT_DIR [--report report.md]

Both directories mirror `outputs/` (e.g. a copy of the committed outputs taken before the
rebuild, and `outputs/` after deleting and regenerating it). Text columns must match exactly;
numeric columns must agree within the tolerance listed per file. PCA/MDS coordinates may flip
sign between linear-algebra libraries, so they are compared up to sign. Exit 1 on any mismatch.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# path relative to outputs/ -> absolute tolerance for numeric columns
FILES = {
    "pet_protein_activity_summary.csv": 1e-9,
    "tables/pet_assay_records.csv": 1e-9,
    "explorer/clean/pet_active_proteins.csv": 0,
    "explorer/clean/qc_checks.csv": 0,
    "explorer/clustering/pairwise_alignment.csv": 1e-4,
    "explorer/clustering/sequence_features.csv": 1e-6,
    "explorer/clustering/cluster_assignments.csv": 1e-4,
    "explorer/clustering/method_comparison.csv": 1e-3,
    "explorer/clustering/null_baseline.csv": 1e-3,
    "explorer/clustering/clustering_selection.json": 1e-3,
    "explorer/matching/leave_one_out_nearest_neighbour.csv": 1e-9,
    "explorer/network/ssn_edges.csv": 1e-4,
    "explorer/temperature/statistical_tests.csv": 1e-6,
    "explorer/temperature/protein_temperature_summary.csv": 1e-9,
    "explorer/organisms/protein_organisms.csv": 0,
    # supervised-model metrics: same seeds, but tree ensembles can differ in the last digits across platforms
    "explorer/prediction/model_comparison.csv": 0.01,
    "explorer/prediction/permutation_test.csv": 0.02,
    "explorer/prediction/threshold_metrics.csv": 0.02,
    "explorer/prediction/prediction_dataset.csv": 0,
    "explorer/shortlist/candidate_shortlist.csv": 0.11,   # z-scores are reported to 0.1
    "explorer/shortlist/shortlist_summary.json": 0,
    "curation/proteins_master.csv": 0,
    "curation/condition_specific_labels.csv": 1e-9,
    "curation/homology_groups.csv": 0,
    "curation/split_assignments.csv": 0,
    "curation/split_diagnostics.json": 1e-9,
    "curation/candidate_eligibility.csv": 1e-9,
}
SIGN_FREE = ("pca1", "pca2", "mds1", "mds2")
TEXT_EXEMPT = {"explorer/prediction/permutation_test.csv": {"model"}}


def compare_csv(ref, new, tol, name):
    a, b = pd.read_csv(ref), pd.read_csv(new)
    if list(a.columns) != list(b.columns):
        return [f"{name}: columns differ"]
    if len(a) != len(b):
        return [f"{name}: {len(a)} rows in reference vs {len(b)} rebuilt"]
    out = []
    for c in a.columns:
        x, y = a[c], b[c]
        if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
            xv, yv = x.to_numpy(float), y.to_numpy(float)
            if c in SIGN_FREE:
                xv, yv = np.abs(xv), np.abs(yv)
            same_nan = np.isnan(xv) == np.isnan(yv)
            close = np.isclose(xv, yv, atol=tol, rtol=0, equal_nan=True)
            if not (same_nan.all() and close.all()):
                bad = int((~close | ~same_nan).sum())
                diff = np.nanmax(np.abs(xv - yv)) if len(xv) else 0
                out.append(f"{name}: column '{c}' differs in {bad} rows (max |diff| {diff:.3g}, tolerance {tol})")
        elif c not in TEXT_EXEMPT.get(name, set()):
            if not (x.fillna("<NA>").astype(str) == y.fillna("<NA>").astype(str)).all():
                bad = int((x.fillna("<NA>").astype(str) != y.fillna("<NA>").astype(str)).sum())
                out.append(f"{name}: text column '{c}' differs in {bad} rows")
    return out


def compare_json(a, b, tol, where):
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return [f"{where}: keys differ"]
        return [m for k in a for m in compare_json(a[k], b[k], tol, f"{where}.{k}")]
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{where}: list lengths differ"]
        return [m for i, (x, y) in enumerate(zip(a, b)) for m in compare_json(x, y, tol, f"{where}[{i}]")]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return [] if abs(a - b) <= tol else [f"{where}: {a} vs {b}"]
    return [] if a == b else [f"{where}: {a!r} vs {b!r}"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reference")
    ap.add_argument("rebuilt")
    ap.add_argument("--report")
    args = ap.parse_args()
    ref, new = Path(args.reference), Path(args.rebuilt)
    rows, problems = [], []
    for name, tol in FILES.items():
        r, n = ref / name, new / name
        if not r.exists():
            rows.append((name, "no reference")); continue
        if not n.exists():
            problems.append(f"{name}: not regenerated"); rows.append((name, "MISSING")); continue
        if name.endswith(".json"):
            msgs = compare_json(json.loads(r.read_text()), json.loads(n.read_text()), tol, name)
        else:
            msgs = compare_csv(r, n, tol, name)
        problems += msgs
        rows.append((name, "ok" if not msgs else f"{len(msgs)} difference(s)"))
    lines = ["# Rebuild vs reference", "", "| File | Result |", "|---|---|"] + [f"| {a} | {b} |" for a, b in rows]
    lines += ["", "## Differences", ""] + ([f"- {p}" for p in problems] or ["- none"])
    report = "\n".join(lines) + "\n"
    print(report)
    if args.report:
        Path(args.report).write_text(report)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
