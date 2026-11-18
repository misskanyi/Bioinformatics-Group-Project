"""Static matplotlib figures (PNG) for the notebook, README and report.
The dashboard draws its own interactive Plotly versions from the same CSVs."""

import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import squareform

from . import config as C

INK, INK2, GRID, GREY = "#0b0b0b", "#52514e", "#e6e5e0", "#a3a29c"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*"]
POS_COLOR, NEG_COLOR = SERIES[0], SERIES[1]


def group_key(label):
    """Sort G1a, G1b, G2 ... G10 naturally."""
    m = re.match(r"G(\d+)([a-z]?)", str(label))
    return (int(m.group(1)), m.group(2)) if m else (10**6, str(label))


def cluster_colors(clusters):
    order = sorted(set(clusters), key=group_key)
    return {c: (SERIES[i % 8], MARKERS[i % 8]) for i, c in enumerate(order)}


def style(ax, grid="y"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9)
    if grid:
        ax.grid(axis=grid, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def title(ax, text):
    ax.set_title(text, loc="left", fontsize=11, fontweight="bold", color=INK)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(C.FIGURES / name, dpi=150)
    plt.close(fig)


def length_distribution(feats):
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax.hist(feats.length, bins=np.arange(170, 500, 10), color=SERIES[0], edgecolor="white", linewidth=1.5)
    med = feats.length.median()
    ax.axvline(med, color=INK2, lw=1, ls="--")
    ax.text(med, ax.get_ylim()[1] * 0.95, f"  median {med:.0f} aa", color=INK2, fontsize=8.5, va="top")
    ax.set_xlabel("Sequence length (amino acids)", color=INK2, fontsize=9)
    ax.set_ylabel("Proteins", color=INK2, fontsize=9)
    title(ax, f"Sequence length of the {len(feats)} PET-active proteins")
    style(ax)
    save(fig, "f01_length_distribution.png")


def composition_bars(feats):
    cols = [f"aa_{a}" for a in C.STANDARD_AA]
    m, s = feats[cols].mean(), feats[cols].std()
    order = m.sort_values(ascending=False).index
    fig, ax = plt.subplots(figsize=(8, 3.8))
    x = np.arange(len(order))
    ax.bar(x, m[order], yerr=s[order], color=SERIES[0], edgecolor="white", linewidth=1.5,
           error_kw={"ecolor": INK2, "elinewidth": 0.8, "capsize": 2})
    ax.set_xticks(x, [c[-1] for c in order])
    ax.set_ylabel("Mean % of residues (± SD)", color=INK2, fontsize=9)
    title(ax, "Amino-acid composition across PET-active proteins")
    style(ax)
    save(fig, "f02_aa_composition.png")


def composition_heatmap(feats, assign):
    cols = [f"aa_{a}" for a in C.STANDARD_AA]
    df = feats.merge(assign[["protein_id", "subcluster"]], on="protein_id")
    tab = df.groupby("subcluster")[cols].mean()
    tab = tab.loc[sorted(tab.index, key=group_key)]
    sizes = df.subcluster.value_counts()
    z = (tab - feats[cols].mean()) / feats[cols].std()
    fig, ax = plt.subplots(figsize=(9, 3.6))
    im = ax.imshow(z.values, cmap="RdBu_r", vmin=-2, vmax=2, aspect="auto")
    ax.set_xticks(range(20), [c[-1] for c in cols])
    ax.set_yticks(range(len(z)), [f"{c} (n={sizes[c]})" for c in z.index])
    cb = fig.colorbar(im, ax=ax, fraction=0.03)
    cb.set_label("Cluster mean vs all proteins (SD units)", fontsize=8, color=INK2)
    title(ax, "Amino-acid composition by cluster")
    style(ax, grid=None)
    save(fig, "f03_aa_composition_by_cluster.png")


def method_comparison(table):
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    for (m, lab), col in zip([("hierarchical_average_alignment", "Hierarchical (alignment)"),
                              ("kmeans_features", "K-means (features)"),
                              ("dbscan_alignment", "DBSCAN (alignment)")], SERIES[:3]):
        t = table[table.method == m]
        axes[0].plot(t.n_clusters, t.silhouette_alignment, marker="o", ms=4, lw=1.8, color=col, label=lab)
        axes[1].plot(t.n_clusters, t.stability_ari_mean, marker="o", ms=4, lw=1.8, color=col, label=lab)
    axes[0].set_ylabel("Silhouette (alignment distance)", color=INK2, fontsize=9)
    axes[1].set_ylabel("Stability (mean ARI, 30 × 80% subsamples)", color=INK2, fontsize=9)
    for ax, t in zip(axes, ["Separation of groups", "Reproducibility of groups"]):
        ax.set_xlabel("Number of clusters", color=INK2, fontsize=9)
        ax.set_xscale("log")
        title(ax, t)
        style(ax)
    axes[0].legend(fontsize=8, frameon=False)
    save(fig, "f04_clustering_method_comparison.png")


def scatter_by_cluster(coords, assign, xlab, ylab, ttl, name):
    df = assign.copy()
    df["x"], df["y"] = coords[:, 0], coords[:, 1]
    colors = cluster_colors(df.subcluster)
    sizes = df.subcluster.value_counts()
    fig, ax = plt.subplots(figsize=(7, 4.8))
    for c, (col, mk) in colors.items():
        g = df[df.subcluster == c]
        ax.scatter(g.x, g.y, s=26, color=col, marker=mk, edgecolor="white", linewidth=0.8,
                   label=f"{c} (n={sizes[c]})", alpha=0.9)
    ax.set_xlabel(xlab, color=INK2, fontsize=9)
    ax.set_ylabel(ylab, color=INK2, fontsize=9)
    ax.legend(fontsize=8, frameon=False, loc="center left", bbox_to_anchor=(1, 0.5))
    title(ax, ttl)
    style(ax, grid="both")
    save(fig, name)


def identity_heatmap(sim, assign):
    dist = 1 - sim
    np.fill_diagonal(dist, 0)
    order = dendrogram(linkage(squareform(np.clip(dist, 0, 1), checks=False), "average"), no_plot=True)["leaves"]
    m = sim[np.ix_(order, order)]
    clusters = assign.subcluster.to_numpy()[order]
    colors = cluster_colors(assign.subcluster)
    fig = plt.figure(figsize=(7.5, 7))
    ax_bar = fig.add_axes([0.08, 0.1, 0.025, 0.8])
    ax = fig.add_axes([0.11, 0.1, 0.72, 0.8])
    cax = fig.add_axes([0.86, 0.3, 0.02, 0.4])
    im = ax.imshow(m * 100, cmap="Blues", vmin=0, vmax=100, interpolation="nearest")
    rgb = np.array([matplotlib.colors.to_rgb(colors[c][0]) for c in clusters])[:, None, :]
    ax_bar.imshow(rgb, aspect="auto", interpolation="nearest")
    ax_bar.set_xticks([]); ax_bar.set_yticks([])
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, cax=cax)
    cb.set_label("% identity (identical residues / shorter length)", fontsize=8, color=INK2)
    ax.set_title("Pairwise sequence identity (proteins ordered by average-linkage tree)",
                 loc="left", fontsize=11, fontweight="bold")
    fig.text(0.08, 0.06, "Left bar = cluster / G1 subgroup", fontsize=8, color=INK2)
    fig.savefig(C.FIGURES / "f07_identity_heatmap.png", dpi=150)
    plt.close(fig)


def cluster_sizes(assign):
    s = assign.subcluster.value_counts()
    s = s.loc[sorted(s.index, key=group_key)]
    fig, ax = plt.subplots(figsize=(7, 3.5))
    x = np.arange(len(s))
    ax.bar(x, s.values, color=SERIES[0], edgecolor="white", linewidth=1.5)
    for xi, v in zip(x, s.values):
        ax.text(xi, v, f"{v}", ha="center", va="bottom", fontsize=9, color=INK)
    ax.set_xticks(x, s.index)
    ax.set_yscale("log")
    ax.set_ylabel("Proteins (log scale)", color=INK2, fontsize=9)
    title(ax, "Cluster sizes (G1 split into subgroups G1a/G1b)")
    style(ax)
    save(fig, "f08_cluster_sizes.png")


def motif_variants(feats):
    v = pd.Series([x for s in feats.gxsxg_variants.fillna("") for x in s.split("; ") if x]).value_counts()
    top = v.head(10)
    fig, ax = plt.subplots(figsize=(7, 3.6))
    y = np.arange(len(top))[::-1]
    ax.barh(y, top.values, color=SERIES[0], height=0.6, edgecolor="white", linewidth=1.5)
    ax.set_yticks(y, top.index, family="monospace")
    for yi, val in zip(y, top.values):
        ax.text(val, yi, f"  {val}", va="center", fontsize=9)
    ax.set_xlabel("Proteins containing the variant", color=INK2, fontsize=9)
    n_with = int((feats.gxsxg_count > 0).sum())
    title(ax, f"G-x-S-x-G motif variants ({n_with}/{len(feats)} proteins have ≥1)")
    style(ax, grid="x")
    save(fig, "f09_gxsxg_motif_variants.png")


def ssn(edges, assign):
    """Static SSN picture. Nodes sit at their alignment-distance MDS position (so the
    layout itself reflects homology); edges are drawn on top."""
    from matplotlib.collections import LineCollection
    df = assign.set_index("protein_id")
    pos = df[["mds1", "mds2"]]
    colors = cluster_colors(df.subcluster)
    sizes = df.subcluster.value_counts()
    fig, ax = plt.subplots(figsize=(8, 6))
    segs = np.stack([pos.loc[edges.source].to_numpy(), pos.loc[edges.target].to_numpy()], axis=1)
    ax.add_collection(LineCollection(segs, colors=GREY, linewidths=0.2, alpha=0.25, zorder=1))
    for c, (col, mk) in colors.items():
        sub = df[df.subcluster == c]
        ax.scatter(sub.mds1, sub.mds2, s=24, color=col, marker=mk, edgecolor="white", linewidth=0.6, zorder=2,
                   label=f"{c} (n={sizes[c]})")
    ax.legend(fontsize=8, frameon=False, loc="center left", bbox_to_anchor=(1, 0.5))
    ax.set_xlabel("MDS axis 1 (alignment distance)", color=INK2, fontsize=9)
    ax.set_ylabel("MDS axis 2", color=INK2, fontsize=9)
    title(ax, f"Sequence-similarity network: {len(df)} proteins, {len(edges):,} edges\n"
              f"(edge = ≥40% identity over ≥70% of both proteins)")
    style(ax, grid=None)
    save(fig, "f11_similarity_network.png")


def model_comparison(table, n, n_pos):
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6), sharey=True)
    t = table.iloc[::-1]
    y = np.arange(len(t))
    colors = [GREY if k == "baseline" else SERIES[0] for k in t.kind]
    for ax, m, lab in zip(axes, ["roc_auc", "balanced_accuracy"], ["ROC AUC", "Balanced accuracy"]):
        ax.barh(y, t[f"{m}_mean"], xerr=t[f"{m}_sd"], color=colors, height=0.6, edgecolor="white",
                error_kw={"ecolor": INK2, "lw": 1})
        ax.axvline(0.5, color=INK2, lw=1, ls="--")
        for yi, v in zip(y, t[f"{m}_mean"]):
            ax.text(0.02, yi, f"{v:.2f}", va="center", fontsize=8.5, color="white")
        ax.set_xlim(0, 1)
        ax.set_xlabel(f"{lab} (mean ± sd, 20 × grouped 5-fold CV)", color=INK2, fontsize=9)
        style(ax, grid="x")
    axes[0].set_yticks(y, t.model)
    title(axes[0], f"Predicting PET conversion at 60 °C")
    title(axes[1], f"n={n} ({n_pos} detected). Grey = baseline")
    save(fig, "f10_prediction_models.png")


EVAL_MODELS = ["logistic regression (features)", "random forest (features)", "5-NN on alignment identity"]


def cv_evaluation(oof, folds, null, perm):
    """Evaluation figures for the 60 °C model, all from held-out (out-of-fold) predictions of
    the same 20 x grouped 5-fold CV that produced model_comparison.csv."""
    from sklearn.metrics import roc_auc_score, roc_curve

    # f12 - ROC curves: one thin line per repeat (pooled out-of-fold scores), bold = mean curve
    grid = np.linspace(0, 1, 101)
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 4.3), sharey=True)
    for ax, m, col in zip(axes, EVAL_MODELS, SERIES):
        tprs, aucs = [], []
        for _, g in oof[oof.model == m].groupby("repeat"):
            fpr, tpr, _ = roc_curve(g.detected_at_60c, g.score)
            ax.plot(fpr, tpr, color=col, alpha=0.18, lw=0.8)
            tprs.append(np.interp(grid, fpr, tpr))
            aucs.append(roc_auc_score(g.detected_at_60c, g.score))
        ax.plot(grid, np.mean(tprs, axis=0), color=col, lw=2.2)
        ax.plot([0, 1], [0, 1], color=INK2, lw=1, ls="--")
        ax.text(0.97, 0.05, f"pooled AUC {np.mean(aucs):.2f} ± {np.std(aucs):.2f}\n(20 repeats)",
                ha="right", fontsize=8.5, color=INK2)
        ax.set_xlabel("False-positive rate", color=INK2, fontsize=9)
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)
        style(ax, grid="both")
        title(ax, m.replace(" (features)", ""))
    axes[0].set_ylabel("True-positive rate", color=INK2, fontsize=9)
    save(fig, "f12_roc_curves.png")

    # f13 - confusion matrices at the 0.5 cut-off, summed over held-out folds / 20 repeats
    ok = folds[~folds.skipped_single_class]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8))
    for ax, m in zip(axes, EVAL_MODELS):
        g = ok[ok.model == m]
        cm = np.array([[g.tn.sum(), g.fp.sum()], [g.fn.sum(), g.tp.sum()]]) / g.repeat.nunique()
        ax.imshow(cm, cmap="Blues", vmin=0, vmax=max(cm.max(), 1))
        for (i, j), v in np.ndenumerate(cm):
            ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=11,
                    color="white" if v > cm.max() * 0.6 else INK)
        ax.set_xticks([0, 1], ["predicted\nnot detected", "predicted\ndetected"], fontsize=8.5)
        ax.set_yticks([0, 1], ["not detected", "detected"], fontsize=8.5)
        title(ax, m.replace(" (features)", ""))
    fig.suptitle("Held-out predictions at score ≥ 0.5 (rows = measured outcome), "
                 "average of 20 repeats of grouped 5-fold CV", fontsize=9.5, color=INK2)
    save(fig, "f13_confusion_matrices.png")

    # f14 - permutation null
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.hist(null, bins=25, color=GREY, edgecolor="white")
    obs = perm["observed_roc_auc"]
    ax.axvline(obs, color=SERIES[1], lw=2)
    ax.axvline(perm["null_95th_percentile"], color=INK2, lw=1, ls="--")
    ax.text(obs, ax.get_ylim()[1] * 0.95, f"  observed {obs:.3f}\n  p = {perm['empirical_p']}",
            color=SERIES[1], fontsize=9, va="top")
    ax.text(perm["null_95th_percentile"], ax.get_ylim()[1] * 0.6, "  95th percentile\n  of null", color=INK2,
            fontsize=8.5, va="top")
    ax.set_xlabel(f"ROC AUC with shuffled labels ({perm['n_permutations']} permutations)", color=INK2, fontsize=9)
    ax.set_ylabel("count", color=INK2, fontsize=9)
    style(ax)
    title(ax, f"Permutation test: {perm['model']}")
    save(fig, "f14_permutation_null.png")

    # f15 - per-fold ROC AUC for every model and baseline
    order = list(dict.fromkeys(folds.model))
    fig, ax = plt.subplots(figsize=(9, 3.8))
    rng = np.random.default_rng(0)
    for i, m in enumerate(order):
        v = ok[ok.model == m].roc_auc.to_numpy()
        base = folds[folds.model == m].kind.iloc[0] == "baseline"
        ax.scatter(i + rng.uniform(-0.18, 0.18, len(v)), v, s=9, alpha=0.45,
                   color=GREY if base else SERIES[0], edgecolors="none")
        ax.hlines(np.mean(v), i - 0.3, i + 0.3, color=INK, lw=2)
    ax.axhline(0.5, color=INK2, lw=1, ls="--")
    ax.set_xticks(range(len(order)), [m.replace(" (features)", "").replace(" on alignment identity", "")
                                      for m in order], fontsize=8.5)
    ax.set_ylim(0, 1.02)
    ax.set_ylabel("ROC AUC of one held-out fold", color=INK2, fontsize=9)
    style(ax)
    n_eval = int((ok.model == order[0]).sum())
    title(ax, f"Every evaluated held-out fold ({n_eval} per model; bar = mean). Grey = baseline")
    save(fig, "f15_cv_folds.png")
