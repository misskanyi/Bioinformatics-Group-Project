"""Gate for condition-specific activity predictions.

A prediction is only served when (1) pet_explorer.prediction produced a model
that beat its shuffled-label null (permutation p < 0.05) and (2) that fitted
model was persisted for scoring. The pipeline currently persists no model and
its best model does not clear the null, so every sequence is reported as
"Prediction not available" together with the reason, read from the outputs.
Nothing in this module produces a score.
"""

from functools import lru_cache

from pet_explorer import config as C

from . import store

ALPHA = 0.05
MODEL_ARTIFACT = C.PREDICTION / "model.joblib"   # not written by the current pipeline

# The only condition the model was ever trained for (see backend/api/modelling.py TARGET).
CONDITION = {
    "target": "PET conversion detected at 60 °C",
    "temperature_c": 60,
    "substrate": "crystalline PET powder",
    "protocol": "standardised screen, DOI 10.1021/acscatal.5c03460",
}


@lru_cache
def status() -> dict:
    perm = store.permutation_test()
    p = float(perm.empirical_p.iloc[0]) if perm is not None and len(perm) else None
    model = str(perm.model.iloc[0]) if perm is not None and len(perm) else None
    auc = float(perm.observed_roc_auc.iloc[0]) if perm is not None and len(perm) else None

    if p is None:
        reason = "Model validation outputs have not been generated."
    elif p >= ALPHA:
        reason = (f"The best cross-validated model ({model}, ROC AUC {auc:.3f}) does not beat a "
                  f"shuffled-label null (permutation p = {p}), so its scores would not mean anything.")
    elif not MODEL_ARTIFACT.exists():
        reason = "The validated model was not persisted, so it cannot score new sequences."
    else:  # pragma: no cover - no validated, persisted model exists in this repository
        reason = "A validated model exists but no scoring service has been connected to it."
    return {"available": False, "reason": reason, "condition": CONDITION,
            "model": model, "roc_auc": auc, "permutation_p": p}


def for_sequence() -> dict:
    """Per-sequence prediction block: always explicit, never a placeholder number."""
    s = status()
    return {"status": "not_available", "label": "Prediction not available", "reason": s["reason"],
            "condition": s["condition"], "score": None}
