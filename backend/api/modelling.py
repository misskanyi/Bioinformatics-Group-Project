"""Model Validation: the supervised model actually trained by pet_explorer.prediction,
plus the dataset audit that defines what can and cannot be modelled.

Nothing here trains, scores or predicts. Every number comes from
outputs/explorer/prediction/* or outputs/dataset_audit/*. When a file has not
been generated the field is null and the client shows a pending state, so the
page can never display an invented metric.
"""

from fastapi import APIRouter

from ..services import store

router = APIRouter()

TARGET = {
    "label": "PET conversion detected at 60 °C",
    "definition": "Maximum conversion > 0 at the highest tested temperature (60 °C) in the "
                  "standardised screen of DOI 10.1021/acscatal.5c03460.",
    "why": "PET-active vs PET-inactive cannot be learned: the curated set contains 0 usable "
           "PET-inactive sequences. The standardised screen is the only place where many proteins "
           "were measured under one protocol at 40 and 60 °C, which gives a balanced, "
           "condition-qualified target.",
    "features": "20 amino-acid frequencies, length, isoelectric point, GRAVY, aromaticity, "
                "instability index and helix/turn/sheet propensity (pet_explorer.features.ML_FEATURES).",
    "splitting": "20 repeats of 5-fold StratifiedGroupKFold grouped by 70%-identity group, so no "
                 "test protein has a >= 70%-identical relative in its training fold.",
    "metrics": "ROC AUC and balanced accuracy, averaged over folds; folds whose test set holds one "
               "class only are skipped.",
}

LIMITATIONS = [
    ("Few independent scaffolds", "78 proteins fall into only 19 groups at 70% identity, so the "
     "effective sample size is far smaller than the protein count and confidence intervals are wide."),
    ("Class imbalance varies by condition", "The screen is near-balanced at 40 °C on crystalline "
     "powder (47-54% positive) but drops to 0% positive on amorphous film at 60 °C and pH 8.5. "
     "No condition-free claim of activity is meaningful."),
    ("Detection limits", "A zero means the reported method measured no product above its detection "
     "limit under those conditions. It does not prove the enzyme is inactive."),
    ("Leakage risk between sources", "128 of 214 assayed screen enzymes are >= 99% identical to a "
     "PAZy protein, and 329 of 501 PETML entries are >= 99% identical to a PAZy protein. Any "
     "train/test split made on source file rather than sequence identity is invalid."),
    ("Publication bias", "244 of 501 PETML entries are IsPETase derivatives; the literature "
     "over-samples scaffolds that already worked."),
    ("Substrate and assay differences", "Crystalline powder and amorphous film give different "
     "outcomes for the same enzyme, and assay units differ between papers, so activity values are "
     "never pooled across studies."),
    ("Generalisation", "The model was evaluated only inside one screen. Its behaviour on proteins "
     "unlike that library is unknown."),
]


def _rows(df):
    return store.records(df) if df is not None else None


@router.get("/modelling")
def modelling():
    comparison = store.model_comparison()
    perm = store.permutation_test()
    dataset = store.prediction_dataset()
    audit = store.audit_statistics()

    summary = None
    if dataset is not None:
        y = dataset.detected_at_60c
        summary = {
            "n_proteins": int(len(dataset)),
            "n_positive": int(y.sum()),
            "n_negative": int((y == 0).sum()),
            "n_identity_groups": int(dataset.identity_group_70.nunique()),
            "by_subcluster": [{"subcluster": s, "n": int(len(g)), "positive": int(g.detected_at_60c.sum())}
                              for s, g in dataset.groupby("subcluster")],
            "group_sizes": sorted(dataset.identity_group_70.value_counts().tolist(), reverse=True),
        }

    best = None
    if comparison is not None:
        m = comparison[comparison.kind == "model"].sort_values("roc_auc_mean", ascending=False)
        if len(m):
            best = store.records(m.head(1))[0]

    return {
        "available": comparison is not None,
        "target": TARGET,
        "dataset": summary,
        "comparison": _rows(comparison),
        "best_model": best,
        "permutation_test": (store.records(perm)[0] if perm is not None and len(perm) else None),
        "feature_importance": _rows(store.feature_importance()),
        "statistical_tests": _rows(store.statistical_tests()),
        "clustering_null": _rows(store.null_baseline()),
        "limitations": [{"title": t, "detail": d} for t, d in LIMITATIONS],
        "candidates": {
            "available": False,
            "reason": "No trained model is persisted and no candidate scores have been produced. "
                      "The cross-validated model does not separate the classes better than chance "
                      "(see the permutation test), so ranking untested sequences with it would not "
                      "be defensible. Candidate ranking is pending a model that clears its null.",
            "pool": (audit or {}).get("si_protein_labels", {}).get("library_never_assayed"),
            "pool_source": "Sequences in the 2025 screening library that were never assayed "
                           "(outputs/dataset_audit/audit_statistics.json).",
        },
        "notes": [
            "Scores are out-of-fold cross-validation means over 20 repeats, not test-set scores from "
            "a single split.",
            "A model is only meaningful if it beats both the majority-class baseline and a "
            "shuffled-label null.",
        ],
    }


@router.get("/audit")
def audit():
    """Dataset-level feasibility facts used by the data preparation page."""
    stats = store.audit_statistics()
    if stats is None:
        return {"available": False}
    labels = stats.get("labels", {})
    return {
        "available": True,
        "pazy": labels.get("pazy_pet_measurements"),
        "screen_labels": labels.get("si_protein_labels"),
        "condition_labels": labels.get("si_condition_labels"),
        "replicates": labels.get("si_replicates"),
        "overlap": stats.get("overlap"),
        "library": (stats.get("si2025") or {}).get("rounds"),
        "assay_table": (stats.get("si2025") or {}).get("activity"),
    }
