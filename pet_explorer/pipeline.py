"""Run the PET Enzyme Explorer analysis and cache every result to outputs/explorer/.

    .venv/bin/python -m pet_explorer.pipeline            # all stages
    .venv/bin/python -m pet_explorer.pipeline --stage 2  # one stage (earlier outputs must exist)
    .venv/bin/python -m pet_explorer.pipeline --recompute-alignments
"""

import argparse
import json

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score

from . import clustering, config as C, features, network, plots, preprocess, similarity


# --------------------------------------------------------------------------- #
def stage1():
    proteins, qc = preprocess.run()
    print(f"[stage 1] {len(proteins)} PET-active proteins written to {C.F_PROTEINS.relative_to(C.ROOT)}")
    print(qc.to_string(index=False))
    return proteins


# --------------------------------------------------------------------------- #
def stage2(recompute=False):
    proteins = preprocess.load_proteins()
    ids = proteins.protein_id.tolist()
    pairs = similarity.compute_pairs(proteins, reuse=not recompute)
    sim = similarity.square_matrix(pairs, ids)

    feats = features.feature_table(proteins)
    feats.to_csv(C.CLUSTERING / "sequence_features.csv", index=False)

    table, labels = clustering.compare_methods(sim, feats)
    table.to_csv(C.CLUSTERING / "method_comparison.csv", index=False)
    best = clustering.select_final(table, len(ids))
    final = labels[(best.method, best.parameter)]

    # name clusters G1..Gn by size (largest = G1)
    order = pd.Series(final).value_counts().index
    rename = {old: f"G{n}" for n, old in enumerate(order, 1)}
    assign = pd.DataFrame({"protein_id": ids, "protein_name": proteins.protein_name,
                           "cluster": [rename[x] for x in final]})
    km = labels[("kmeans_features", int(best.parameter))] if best.method != "kmeans_features" else final
    assign["kmeans_same_k"] = km
    assign["dbscan_eps0.5"] = labels[("dbscan_alignment", 0.5)]
    groups70 = clustering.single_linkage_groups(pairs, ids, 0.70)
    assign["identity_group_70"] = assign.protein_id.map(groups70)
    pca_xy, pca_var = clustering.pca_coordinates(feats)
    mds_xy, mds_var = clustering.mds_coordinates(clustering.distance_matrix(sim))
    assign[["pca1", "pca2"]] = pca_xy
    assign[["mds1", "mds2"]] = mds_xy
    assign.to_csv(C.CLUSTERING / "cluster_assignments.csv", index=False)

    # level 2: internal structure of the dominant group G1
    g1 = np.where(assign.cluster == "G1")[0]
    sub_table, sub_labels = clustering.subgroup_compare(sim, g1)
    sub_table.to_csv(C.CLUSTERING / "g1_subgroup_comparison.csv", index=False)
    sub_best = clustering.select_subgroups(sub_table)
    assign["subcluster"] = assign.cluster
    if sub_best is not None:
        lab = sub_labels[(sub_best.method, int(sub_best.k))]
        letters = {old: chr(97 + n) for n, old in enumerate(pd.Series(lab).value_counts().index)}
        assign.loc[g1, "subcluster"] = ["G1" + letters[x] for x in lab]
    assign.to_csv(C.CLUSTERING / "cluster_assignments.csv", index=False)

    # summaries per subcluster (G1a, G1b, G2 ... G7)
    kmers = features.cluster_kmers(proteins, assign.subcluster.tolist())
    kmers.to_csv(C.CLUSTERING / "cluster_specific_kmers.csv", index=False)
    rows = []
    for c, g in assign.groupby("subcluster"):
        idx = g.index.to_numpy()
        f = feats.iloc[idx]
        within = sim[np.ix_(idx, idx)][np.triu_indices(len(idx), 1)]
        variants = pd.Series([v for s in f.gxsxg_variants.fillna("") for v in s.split("; ") if v]).value_counts()
        dois = proteins.dois.iloc[idx].str.split("; ").explode().value_counts()
        mean_within = round(100 * within.mean(), 1) if len(within) else None
        rows.append({
            "subcluster": c, "cluster": g.cluster.iloc[0], "n_proteins": len(g),
            "median_length": int(f.length.median()), "length_range": f"{f.length.min()}-{f.length.max()}",
            "mean_within_identity_pct": mean_within,
            "coherence": ("single protein" if mean_within is None else
                          "coherent (mean identity >= 40%)" if mean_within >= 40 else
                          "moderate (25-40%)" if mean_within >= 25 else
                          "heterogeneous (< 25%) - remainder group, not a family"),
            "with_gxsxg": f"{int((f.gxsxg_count > 0).sum())}/{len(g)}",
            "top_gxsxg_variants": "; ".join(f"{k} ({v})" for k, v in variants.head(3).items()),
            "median_pI": round(f.isoelectric_point.median(), 2),
            "n_specific_5mers": int((kmers.cluster == c).sum()),
            "n_publications": int(len(dois)),
            "top_publication_share": f"{dois.index[0]} ({dois.iloc[0]}/{len(g)})",
            "example_members": ", ".join(g.protein_name.head(10)),
        })
    csum = pd.DataFrame(rows).sort_values("subcluster", key=lambda s: s.map(plots.group_key))
    csum.to_csv(C.CLUSTERING / "cluster_summary.csv", index=False)

    agreement = {
        "final_method": best.method, "final_parameter": float(best.parameter),
        "ari_final_vs_kmeans_same_k": round(adjusted_rand_score(final, km), 3),
        "ari_final_vs_dbscan_eps0.5": round(adjusted_rand_score(final, assign["dbscan_eps0.5"]), 3),
        "ari_final_vs_identity_group_70": round(adjusted_rand_score(final, assign.identity_group_70), 3),
        "n_identity_groups_70": int(assign.identity_group_70.nunique()),
        "pca_variance_explained": [round(float(v), 3) for v in pca_var],
        "mds_variance_explained": [round(float(v), 3) for v in mds_var],
    }
    plain = lambda row: None if row is None else {k: (v.item() if hasattr(v, "item") else v) for k, v in row.items()}
    (C.CLUSTERING / "clustering_selection.json").write_text(json.dumps(
        {**agreement, "selected_row": plain(best), "g1_subgroup_selected": plain(sub_best)}, indent=2))

    # figures
    plots.length_distribution(feats)
    plots.composition_bars(feats)
    plots.composition_heatmap(feats, assign)
    plots.method_comparison(table)
    plots.scatter_by_cluster(pca_xy, assign, f"PC1 ({100 * pca_var[0]:.0f}% of variance)",
                             f"PC2 ({100 * pca_var[1]:.0f}%)",
                             "PCA of composition + physicochemical features", "f05_pca_features.png")
    plots.scatter_by_cluster(mds_xy, assign, "MDS axis 1", "MDS axis 2",
                             "Map of alignment distances (classical MDS)", "f06_mds_alignment.png")
    plots.identity_heatmap(sim, assign)
    plots.cluster_sizes(assign)
    plots.motif_variants(feats)

    print(f"[stage 2] selected {best.method} parameter={best.parameter}: "
          f"silhouette={best.silhouette_alignment}, stability ARI={best.stability_ari_mean}")
    print("[stage 2] G1 subgroups:", None if sub_best is None else dict(sub_best))
    print(csum.drop(columns="example_members").to_string(index=False))
    print(json.dumps(agreement, indent=1))
    return assign, pairs


def export_network():
    """Build the SSN with whatever node annotations exist (organism added after stage 4)."""
    proteins = preprocess.load_proteins()
    pairs = pd.read_csv(C.F_PAIRS)
    assign = pd.read_csv(C.CLUSTERING / "cluster_assignments.csv")
    nodes = proteins[["protein_id", "protein_name", "sequence_length", "pet_label", "label_confidence"]].merge(
        assign[["protein_id", "cluster", "identity_group_70"]], on="protein_id")
    org_file = C.ORGANISMS / "protein_organisms.csv"
    if org_file.exists():
        org = pd.read_csv(org_file)[["protein_id", "organism", "taxonomy_id", "organism_evidence"]]
        nodes = nodes.merge(org, on="protein_id", how="left")
    temp_file = C.TEMPERATURE / "protein_temperature_summary.csv"
    if temp_file.exists():
        t = pd.read_csv(temp_file)[["protein_id", "temperatures_tested_c", "temperatures_with_activity_c"]]
        nodes = nodes.merge(t, on="protein_id", how="left")
    g = network.build_graph(nodes, pairs)
    n, e = network.export_cytoscape(g, C.NETWORK)
    network.sensitivity(pairs, nodes.protein_id.tolist()).to_csv(C.NETWORK / "edge_threshold_sensitivity.csv", index=False)
    network.layout(g).to_csv(C.NETWORK / "ssn_layout.csv", index=False)
    import networkx as nx
    comps = sorted((len(c) for c in nx.connected_components(g)), reverse=True)
    print(f"[network] {g.number_of_nodes()} nodes, {g.number_of_edges()} edges, "
          f"{len(comps)} components (largest {comps[0]}, isolated {comps.count(1)})")


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=int, choices=[1, 2, 3, 4])
    ap.add_argument("--recompute-alignments", action="store_true")
    args = ap.parse_args()
    C.ensure_dirs()
    stages = [args.stage] if args.stage else [1, 2, 3, 4]
    if 1 in stages:
        stage1()
    if 2 in stages:
        stage2(args.recompute_alignments)
    if 3 in stages:
        from . import temperature
        temperature.run()
    if 4 in stages:
        from . import organisms
        organisms.run()
    export_network()


if __name__ == "__main__":
    main()
