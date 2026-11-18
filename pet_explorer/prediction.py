"""Supervised machine learning - does the sequence predict whether PET
conversion is still detected at 60 °C?

Why this target: PET-active vs PET-inactive is impossible (0 inactive
sequences). The 99-protein standardised screen (DOI 10.1021/acscatal.5c03460)
is the only place where many proteins were measured under ONE protocol at
40 and 60 °C. 78 of them have a 60 °C value; conversion was detected (> 0) for
39 and not for 39, giving a balanced binary target. 60 °C sits just below the
glass transition of PET (~65-70 °C), where amorphous chains become mobile, so
activity there matters for recycling.

Leakage control: the screen contains near-identical variants. Folds are
grouped by 70%-identity group (identity_group_70), so no test protein has a
>= 70%-identical relative in its training fold.

Models (out-of-fold scores, 20 repeats of 5-fold StratifiedGroupKFold):
  baselines   majority class, random scores, cluster label only (G1a/G1b rate)
  models      logistic regression and random forest on composition +
              physicochemical features; similarity-weighted 5-nearest
              neighbours on alignment identity (homology transfer)
Metrics: ROC AUC and balanced accuracy. The best model is checked with a
label-permutation test (same CV, labels shuffled).
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config as C, plots, similarity
from .features import ML_FEATURES

N_REPEATS, N_SPLITS, N_PERM, SEED = 20, 5, 200, 42
BASELINES = ["majority class", "random scores", "cluster label only"]


def dataset():
    acs = pd.read_csv(C.TEMPERATURE / "screen_acs_max_conversion_by_temperature.csv", index_col=0)
    acs.columns = acs.columns.astype(float)
    hi = acs.columns.max()
    y = (acs[hi].dropna() > 0).astype(int).rename("detected_at_60c")
    assign = pd.read_csv(C.CLUSTERING / "cluster_assignments.csv").set_index("protein_id").loc[y.index]
    feats = pd.read_csv(C.CLUSTERING / "sequence_features.csv").set_index("protein_id").loc[y.index]
    ids = pd.read_csv(C.F_PROTEINS).protein_id.tolist()
    pos = [ids.index(p) for p in y.index]
    sim = similarity.square_matrix(pd.read_csv(C.F_PAIRS), ids)[np.ix_(pos, pos)]
    return y, feats[ML_FEATURES], assign, sim


def _models(x, sim, cluster, seed):
    rng = np.random.default_rng(seed)

    def knn(tr, te, y, k=5):
        s = sim[np.ix_(te, tr)]
        top = np.argsort(-s, axis=1)[:, :k]
        w = np.take_along_axis(s, top, axis=1)
        return (w * y[tr][top]).sum(1) / w.sum(1)

    def sk(make):
        return lambda tr, te, y: make().fit(x[tr], y[tr]).predict_proba(x[te])[:, 1]

    def by_cluster(tr, te, y):
        rate = pd.Series(y[tr]).groupby(cluster[tr]).mean()
        return np.array([rate.get(c, y[tr].mean()) for c in cluster[te]])

    return {
        "majority class": lambda tr, te, y: np.full(len(te), float(y[tr].mean() > 0.5)),
        "random scores": lambda tr, te, y: rng.random(len(te)),
        "cluster label only": by_cluster,
        "logistic regression (features)": sk(lambda: make_pipeline(StandardScaler(),
                                                                   LogisticRegression(C=0.1, max_iter=5000))),
        "random forest (features)": sk(lambda: RandomForestClassifier(300, min_samples_leaf=3, random_state=seed,
                                                                      n_jobs=-1)),
        "5-NN on alignment identity": knn,
    }


def _cv(fn, y, groups, seed, record=None):
    """Per-fold (ROC AUC, balanced accuracy), so a constant predictor scores exactly 0.5.
    A fold whose test set holds one class only (possible with large identity groups) is skipped.

    If `record` is a list, one dict per fold is appended to it: the held-out indices, their
    out-of-fold scores and whether the fold was skipped. Recording reads the same scores and
    does not change the computation or the random-number stream."""
    out = []
    for k, (tr, te) in enumerate(StratifiedGroupKFold(N_SPLITS, shuffle=True, random_state=seed).split(y, y, groups)):
        if len(set(y[te])) < 2:
            if record is not None:
                record.append({"fold": k, "test": te, "scores": None, "skipped": True})
            continue
        s = fn(tr, te, y)
        out.append((roc_auc_score(y[te], s), balanced_accuracy_score(y[te], s >= 0.5)))
        if record is not None:
            record.append({"fold": k, "test": te, "scores": np.asarray(s, dtype=float), "skipped": False})
    return np.mean(out, axis=0)


def evaluate(y, x, sim, cluster, groups, details=None):
    """Mean +/- sd over repeats of the per-repeat fold means. If `details` is a dict, it is
    filled with {(model, repeat): [fold records]} from the same runs (see _cv)."""
    res = {}
    for r in range(N_REPEATS):
        for name, fn in _models(x, sim, cluster, SEED + r).items():
            rec = [] if details is not None else None
            res.setdefault(name, []).append(_cv(fn, y, groups, SEED + r, rec))
            if details is not None:
                details[(name, r)] = rec
    rows = [{"model": m, "kind": "baseline" if m in BASELINES else "model",
             "roc_auc_mean": round(v[:, 0].mean(), 3), "roc_auc_sd": round(v[:, 0].std(), 3),
             "balanced_accuracy_mean": round(v[:, 1].mean(), 3), "balanced_accuracy_sd": round(v[:, 1].std(), 3)}
            for m, v in ((m, np.array(v)) for m, v in res.items())]
    return pd.DataFrame(rows)


def permutation_test(name, y, x, sim, cluster, groups, observed):
    rng = np.random.default_rng(SEED)
    null = []
    for i in range(N_PERM):
        yp = rng.permutation(y)
        fn = _models(x, sim, cluster, SEED + i)[name]
        null.append(_cv(fn, yp, groups, SEED + i)[0])
    null = np.array(null)
    summary = {"model": name, "observed_roc_auc": observed, "null_mean": round(null.mean(), 3),
               "null_95th_percentile": round(np.percentile(null, 95), 3), "n_permutations": N_PERM,
               "empirical_p": round((1 + (null >= observed).sum()) / (N_PERM + 1), 4)}
    return summary, null


def fold_metrics(details, y):
    """One row per (model, repeat, fold) from the grouped-CV out-of-fold scores.

    Threshold metrics use the same 0.5 cut-off as the balanced accuracy in model_comparison.csv.
    Every number comes from held-out folds only; nothing is computed on training predictions."""
    from sklearn.metrics import f1_score, precision_score, recall_score
    rows = []
    for (model, r), recs in details.items():
        for f in recs:
            row = {"model": model, "kind": "baseline" if model in BASELINES else "model",
                   "repeat": r, "fold": f["fold"], "n_test": len(f["test"]),
                   "n_test_positive": int(y[f["test"]].sum()), "skipped_single_class": f["skipped"]}
            if not f["skipped"]:
                yt, s = y[f["test"]], f["scores"]
                p = (s >= 0.5).astype(int)
                row.update({
                    "roc_auc": roc_auc_score(yt, s), "balanced_accuracy": balanced_accuracy_score(yt, p),
                    "precision": precision_score(yt, p, zero_division=0),
                    "recall": recall_score(yt, p, zero_division=0),
                    "f1": f1_score(yt, p, zero_division=0),
                    "tp": int(((p == 1) & (yt == 1)).sum()), "fp": int(((p == 1) & (yt == 0)).sum()),
                    "tn": int(((p == 0) & (yt == 0)).sum()), "fn": int(((p == 0) & (yt == 1)).sum()),
                })
            rows.append(row)
    return pd.DataFrame(rows)


def threshold_summary(folds):
    """Mean +/- sd of the per-fold threshold metrics, plus the confusion matrix summed over all
    evaluated folds and divided by the number of repeats (= an average single 5-fold run)."""
    ok = folds[~folds.skipped_single_class]
    rows = []
    for m, g in ok.groupby("model", sort=False):
        row = {"model": m, "kind": g.kind.iloc[0], "evaluated_folds": len(g),
               "skipped_folds": int(folds[(folds.model == m)].skipped_single_class.sum())}
        for k in ("precision", "recall", "f1"):
            row[f"{k}_mean"], row[f"{k}_sd"] = round(g[k].mean(), 3), round(g[k].std(ddof=0), 3)
        for k in ("tp", "fp", "tn", "fn"):
            row[f"{k}_per_repeat"] = round(g[k].sum() / N_REPEATS, 2)
        rows.append(row)
    return pd.DataFrame(rows)


def out_of_fold(details, y, ids):
    """Out-of-fold score of every protein in every repeat (proteins in skipped folds get no score)."""
    rows = []
    for (model, r), recs in details.items():
        for f in recs:
            if f["skipped"]:
                continue
            for i, s in zip(f["test"], f["scores"]):
                rows.append({"model": model, "repeat": r, "fold": f["fold"], "protein_id": int(ids[i]),
                             "detected_at_60c": int(y[i]), "score": float(s)})
    return pd.DataFrame(rows)


def feature_importance(y, x, names):
    lr = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=5000)).fit(x, y)
    rf = RandomForestClassifier(300, min_samples_leaf=3, random_state=SEED, n_jobs=-1).fit(x, y)
    t = pd.DataFrame({"feature": names, "logistic_coefficient_std": lr[-1].coef_[0].round(3),
                      "random_forest_importance": rf.feature_importances_.round(4)})
    return t.sort_values("random_forest_importance", ascending=False)


@np.errstate(all="ignore")   # spurious matmul warnings from macOS Accelerate BLAS with numpy 2.0
def run():
    C.ensure_dirs()
    y, feats, assign, sim = dataset()
    yv, x, cluster, groups = y.to_numpy(), feats.to_numpy(), assign.subcluster.to_numpy(), assign.identity_group_70.to_numpy()
    details = {}
    table = evaluate(yv, x, sim, cluster, groups, details)
    table.to_csv(C.PREDICTION / "model_comparison.csv", index=False)
    best = table[table.kind == "model"].sort_values("roc_auc_mean", ascending=False).iloc[0]
    perm, null = permutation_test(best.model, yv, x, sim, cluster, groups, best.roc_auc_mean)
    pd.DataFrame([perm]).to_csv(C.PREDICTION / "permutation_test.csv", index=False)
    pd.DataFrame({"permutation": np.arange(len(null)), "null_roc_auc": null}).to_csv(
        C.PREDICTION / "permutation_null.csv", index=False)
    folds = fold_metrics(details, yv)
    folds.to_csv(C.PREDICTION / "cv_fold_metrics.csv", index=False)
    thr = threshold_summary(folds)
    thr.to_csv(C.PREDICTION / "threshold_metrics.csv", index=False)
    oof = out_of_fold(details, yv, y.index.to_numpy())
    oof.to_csv(C.PREDICTION / "oof_predictions.csv.gz", index=False)
    plots.cv_evaluation(oof, folds, null, perm)
    feature_importance(yv, x, feats.columns).to_csv(C.PREDICTION / "feature_importance.csv", index=False)
    pd.DataFrame({"protein_id": y.index, "detected_at_60c": yv, "subcluster": cluster,
                  "identity_group_70": groups}).to_csv(C.PREDICTION / "prediction_dataset.csv", index=False)
    plots.model_comparison(table, len(y), int(yv.sum()))
    print(f"[prediction] n={len(y)} ({yv.sum()} detected at 60 °C), {len(set(groups))} identity groups")
    print(table.to_string(index=False))
    print(perm)
    return table, perm
