"""Read-only, cross-component integrity checks for the committed system outputs.

Run with: python -m pytest tests/test_system_health.py -q
These tests inspect the checked-in analysis artifacts and app source files. They do not
run pipeline stages or write to outputs/, backend/, or frontend/.
"""

from pathlib import Path

import pandas as pd

from pet_explorer import config as C


def test_runtime_inputs_and_cached_outputs_are_present_and_nonempty():
    paths = [
        C.F_ASSAYS, C.F_CSV, C.F_PROTEINS, C.F_FASTA,
        C.F_ASSAY_RECORDS, C.CLUSTERING / "cluster_assignments.csv",
        C.TEMPERATURE / "pet_temperature_assays.csv",
        C.TEMPERATURE / "protein_temperature_summary.csv",
        C.TEMPERATURE / "comparable_temperature_series.csv",
        C.ORGANISMS / "protein_organisms.csv",
        C.PREDICTION / "prediction_dataset.csv",
        C.PREDICTION / "model_comparison.csv",
        C.PREDICTION / "cv_fold_metrics.csv",
        C.PREDICTION / "oof_predictions.csv.gz",
    ]
    assert all(path.is_file() and path.stat().st_size > 0 for path in paths)


def test_assay_conditions_have_valid_calls_and_missingness_is_preserved():
    assays = pd.read_csv(C.TEMPERATURE / "pet_temperature_assays.csv")
    assert len(assays) > 0
    assert assays.protein_id.notna().all()
    assert set(assays.degradation_detected.dropna()) <= {
        "detected", "not detected", "unclear", "excluded"
    }
    assert assays.loc[assays.degradation_detected == "excluded", "outcome_reason"].notna().all()
    assert assays.temperature_c.dropna().between(-50, 150).all()
    assert assays.ph.dropna().between(0, 14).all()
    # Missing experimental values stay missing; the report must not invent a condition.
    assert assays.temperature_c.isna().any() or assays.ph.isna().any()


def test_assay_comparisons_only_include_series_with_three_or_more_temperatures():
    series = pd.read_csv(C.TEMPERATURE / "comparable_temperature_series.csv")
    assert len(series) > 0
    assert series.n_temperatures.ge(3).all()
    assert series.best_tested_temperature_c.notna().all()
    assert series.best_at_edge.isin(["highest tested", "lowest tested", "interior"]).all()


def test_organism_evidence_and_unknown_rows_are_consistent():
    organisms = pd.read_csv(C.ORGANISMS / "protein_organisms.csv")
    assert len(organisms) == organisms.protein_id.nunique() == 298
    assert organisms.organism_evidence.notna().all()
    unknown = organisms.organism_evidence.eq("none")
    assert organisms.loc[unknown, "organism"].str.startswith("Unknown").all()
    assert organisms.loc[~unknown, "organism"].notna().all()
    assert not organisms.organism.str.contains(r"Escherichia coli", case=False, na=False).any()


def test_model_artifacts_are_finite_bounded_and_match_the_declared_target():
    dataset = pd.read_csv(C.PREDICTION / "prediction_dataset.csv")
    comparison = pd.read_csv(C.PREDICTION / "model_comparison.csv")
    oof = pd.read_csv(C.PREDICTION / "oof_predictions.csv.gz")
    folds = pd.read_csv(C.PREDICTION / "cv_fold_metrics.csv")

    assert dataset.protein_id.is_unique
    assert set(dataset.detected_at_60c.dropna().unique()) <= {0, 1}
    assert {"majority class", "random scores", "cluster label only"} <= set(comparison.model)
    assert comparison.model.is_unique
    assert comparison.roc_auc_mean.between(0, 1).all()
    assert comparison.balanced_accuracy_mean.between(0, 1).all()
    assert set(oof.protein_id) <= set(dataset.protein_id)
    assert oof.score.between(0, 1).all()
    assert set(oof.detected_at_60c.unique()) <= {0, 1}
    assert not folds.empty and folds.model.notna().all()
    assert folds.loc[~folds.skipped_single_class, "roc_auc"].between(0, 1).all()
    # Check grouped evaluation has one held-out fold per protein per repeat at most.
    evaluated = folds.loc[~folds.skipped_single_class]
    assert not evaluated.duplicated(["model", "repeat", "fold"]).any()


def test_web_application_entrypoints_remain_in_place():
    root = C.ROOT
    required = [
        root / "backend" / "main.py",
        root / "backend" / "api" / "conditions.py",
        root / "backend" / "api" / "organisms.py",
        root / "backend" / "api" / "sequence.py",
        root / "backend" / "api" / "modelling.py",
        root / "frontend" / "app" / "conditions" / "page.tsx",
        root / "frontend" / "app" / "organisms" / "page.tsx",
        root / "frontend" / "app" / "sequence-lab" / "page.tsx",
        root / "frontend" / "features" / "conditions" / "conditions-view.tsx",
        root / "frontend" / "features" / "organisms" / "organisms-view.tsx",
    ]
    assert all(path.is_file() for path in required)
