"""Feature 2 - unsupervised grouping of the PET-active proteins.

Three method families are compared on the same 298 proteins:

1. Hierarchical clustering (average linkage / UPGMA) on alignment distance
   d = 1 - identity_shorter (identical residues / shorter sequence length).
2. K-means on standardised alignment-free features (amino-acid composition,
   length, physicochemical properties).
3. DBSCAN on the alignment distance matrix (density-based; leaves outliers
   as "noise" rather than forcing them into a group).

Every configuration is scored with the SAME yardsticks so they are comparable:
  * silhouette on alignment distance (do groups reflect sequence homology?)
  * silhouette in standardised feature space
  * stability: mean adjusted Rand index (ARI) between the full-data partition
    and partitions of 30 random 80% subsamples
  * mean within-cluster identity and fraction of within-cluster pairs that
    are >= 40% identical (biological coherence)
  * size of the largest cluster, number of singletons, DBSCAN noise
"""

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from sklearn.cluster import DBSCAN, KMeans, SpectralClustering
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from . import config as C
from .features import ML_FEATURES

N_BOOT, BOOT_FRAC, SEED = 30, 0.8, 42


def distance_matrix(sim):
    d = 1.0 - sim
    np.fill_diagonal(d, 0.0)
    return np.clip(d, 0, 1)


def hierarchical(dist, k):
    z = linkage(squareform(dist, checks=False), method="average")
    return fcluster(z, k, criterion="maxclust") - 1


def kmeans(x, k, seed=SEED):
    return KMeans(n_clusters=k, n_init=10, random_state=seed).fit_predict(x)


def dbscan(dist, eps, min_samples=3):
    return DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed").fit_predict(dist)


def _silhouette(data, labels, metric):
    mask = labels >= 0                      # DBSCAN noise excluded
    if len(set(labels[mask])) < 2 or mask.sum() <= len(set(labels[mask])):
        return np.nan
    if metric == "precomputed":
        return float(silhouette_score(data[np.ix_(mask, mask)], labels[mask], metric="precomputed"))
    return float(silhouette_score(data[mask], labels[mask]))


def _coherence(sim, labels):
    same = (labels[:, None] == labels[None, :]) & (labels[:, None] >= 0)
    iu = np.triu_indices(len(labels), 1)
    s = same[iu]
    vals = sim[iu][s]
    return (float(vals.mean()) if len(vals) else np.nan,
            float((vals >= 0.40).mean()) if len(vals) else np.nan)


def _stability(fn, n, full_labels, rng):
    scores = []
    for _ in range(N_BOOT):
        idx = np.sort(rng.choice(n, int(BOOT_FRAC * n), replace=False))
        scores.append(adjusted_rand_score(full_labels[idx], fn(idx)))
    return float(np.mean(scores)), float(np.std(scores))


def evaluate(method, param, labels, dist, sim, x, fn_sub, rng):
    sizes = pd.Series(labels[labels >= 0]).value_counts()
    within_id, frac40 = _coherence(sim, labels)
    stab, stab_sd = _stability(fn_sub, len(labels), labels, rng)
    return {
        "method": method,
        "parameter": param,
        "n_clusters": int(len(sizes)),
        "noise_points": int((labels < 0).sum()),
        "singletons": int((sizes == 1).sum()),
        "largest_cluster_fraction": round(float(sizes.max() / len(labels)), 3),
        "silhouette_alignment": round(_silhouette(dist, labels, "precomputed"), 3),
        "silhouette_features": round(_silhouette(x, labels, "euclidean"), 3),
        "stability_ari_mean": round(stab, 3),
        "stability_ari_sd": round(stab_sd, 3),
        "mean_within_identity": round(within_id, 3),
        "within_pairs_ge40pct": round(frac40, 3),
    }


def compare_methods(sim, feats):
    """Grid over parameters for the three methods; returns evaluation table and labels."""
    rng = np.random.default_rng(SEED)
    dist = distance_matrix(sim)
    x = StandardScaler().fit_transform(feats[ML_FEATURES].to_numpy())
    rows, labels = [], {}

    for k in list(range(2, 31)) + [35, 40, 50, 60, 80]:
        lab = hierarchical(dist, k)
        fn = lambda idx, k=k: hierarchical(dist[np.ix_(idx, idx)], k)
        rows.append(evaluate("hierarchical_average_alignment", k, lab, dist, sim, x, fn, rng))
        labels[("hierarchical_average_alignment", k)] = lab

    for k in range(2, 31):
        lab = kmeans(x, k)
        fn = lambda idx, k=k: kmeans(StandardScaler().fit_transform(feats[ML_FEATURES].to_numpy()[idx]), k,
                                     seed=int(rng.integers(1e6)))
        rows.append(evaluate("kmeans_features", k, lab, dist, sim, x, fn, rng))
        labels[("kmeans_features", k)] = lab

    for eps in [0.3, 0.4, 0.5, 0.6, 0.7]:
        lab = dbscan(dist, eps)
        fn = lambda idx, eps=eps: dbscan(dist[np.ix_(idx, idx)], eps)
        rows.append(evaluate("dbscan_alignment", eps, lab, dist, sim, x, fn, rng))
        labels[("dbscan_alignment", eps)] = lab

    return pd.DataFrame(rows), labels


def select_final(table, n_proteins, min_stability=0.9, max_noise=0.05, min_within=0.40, tie=0.01):
    """Selection rule (stated before looking at cluster contents):
    1. stable: mean subsample ARI >= 0.9
    2. nearly every protein assigned: DBSCAN noise <= 5%
    3. coherent: mean within-cluster identity >= 40% (above the twilight zone)
    4. highest silhouette on alignment distance; configurations within 0.01
       of the best are treated as tied and the most stable one wins."""
    ok = table[(table.stability_ari_mean >= min_stability)
               & (table.noise_points <= max_noise * n_proteins)
               & (table.mean_within_identity >= min_within)]
    if ok.empty:
        ok = table
    best = ok.silhouette_alignment.max()
    tied = ok[ok.silhouette_alignment >= best - tie]
    return tied.sort_values(["stability_ari_mean", "silhouette_alignment"], ascending=False).iloc[0]


def _mds(dist, k=10):
    n = len(dist)
    j = np.eye(n) - np.ones((n, n)) / n
    w, v = np.linalg.eigh(-0.5 * j @ (dist ** 2) @ j)
    o = np.argsort(w)[::-1][:k]
    return v[:, o] * np.sqrt(np.maximum(w[o], 0))


SUB_METHODS = {
    "hierarchical_average": lambda d, k, s: hierarchical(d, k),
    "hierarchical_complete": lambda d, k, s: fcluster(linkage(squareform(d, checks=False), "complete"), k, "maxclust") - 1,
    "spectral_similarity": lambda d, k, s: SpectralClustering(k, affinity="precomputed", random_state=s)
    .fit_predict(np.clip(1 - d, 0, 1)),
    "kmeans_on_mds": lambda d, k, s: KMeans(k, n_init=10, random_state=s).fit_predict(_mds(d)),
}


def subgroup_compare(sim, members, ks=range(2, 9)):
    """Second-level clustering inside one large group (e.g. G1).
    Average linkage tends to peel off outliers one by one in a dense
    continuum, so partitioning methods are compared as well."""
    rng = np.random.default_rng(SEED)
    sub = sim[np.ix_(members, members)]
    d = distance_matrix(sub)
    rows, labels = [], {}
    for name, fn in SUB_METHODS.items():
        for k in ks:
            lab = fn(d, k, SEED)
            f = lambda idx, k=k, fn=fn: fn(d[np.ix_(idx, idx)], k, int(rng.integers(1_000_000)))
            stab, _ = _stability(f, len(members), lab, rng)
            sizes = pd.Series(lab).value_counts()
            within, _ = _coherence(sub, lab)
            rows.append({"method": name, "k": k,
                         "silhouette_alignment": round(_silhouette(d, lab, "precomputed"), 3),
                         "stability_ari_mean": round(stab, 3),
                         "largest_subgroup_fraction": round(float(sizes.max() / len(lab)), 3),
                         "singletons": int((sizes == 1).sum()),
                         "mean_within_identity": round(within, 3)})
            labels[(name, k)] = lab
    return pd.DataFrame(rows), labels


def select_subgroups(table, min_stability=0.95, max_largest=0.9):
    """Most reproducible genuine split: stability >= 0.95 and no subgroup holding
    > 90% of members (otherwise the 'split' only removes outliers); ties on
    stability broken by silhouette, then by fewer subgroups."""
    ok = table[(table.stability_ari_mean >= min_stability) & (table.largest_subgroup_fraction <= max_largest)]
    if ok.empty:
        return None
    return ok.sort_values(["stability_ari_mean", "silhouette_alignment", "k"],
                          ascending=[False, False, True]).iloc[0]


def single_linkage_groups(pairs, ids, threshold, column="identity_shorter"):
    """Connected components of pairs with similarity >= threshold."""
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in pairs.loc[pairs[column] >= threshold, ["protein_id_a", "protein_id_b"]].itertuples(index=False):
        parent[find(a)] = find(b)
    roots = {i: find(i) for i in ids}
    order = {r: n for n, r in enumerate(pd.Series(list(roots.values())).value_counts().index, 1)}
    return {i: order[r] for i, r in roots.items()}


def pca_coordinates(feats):
    x = StandardScaler().fit_transform(feats[ML_FEATURES].to_numpy())
    pca = PCA(n_components=2, random_state=SEED).fit(x)
    return pca.transform(x), pca.explained_variance_ratio_


def mds_coordinates(dist):
    """2-D embedding of the alignment distance matrix (classical MDS)."""
    n = len(dist)
    j = np.eye(n) - np.ones((n, n)) / n
    w = np.linalg.eigvalsh(-0.5 * j @ (dist ** 2) @ j)
    top = np.sort(w)[::-1][:2]
    return _mds(dist, 2), top / w[w > 0].sum()
